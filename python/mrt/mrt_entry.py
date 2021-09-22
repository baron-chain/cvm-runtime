from os import path
import logging
import json

import mxnet as mx

from mrt.gluon_zoo import save_model
from mrt.common import log
from mrt import utils
from mrt.transformer import Model
from mrt import dataset as ds

default_batch = 16
default_ctx = mx.cpu()

def get_model_prefix(model_dir, model_name):
    if model_dir.startswith("~"):
        model_dir = path.expanduser(model_dir)
    assert path.exists(model_dir), \
        "model_dir: {} does not exist".format(model_dir)
    model_prefix = path.join(model_dir, model_name)
    return model_prefix

def get_logger(verbosity):
    log.Init(log.name2level(verbosity.upper()))
    logger = logging.getLogger("log.main")
    return logger

def set_batch(input_shape, batch):
    """Get the input shape with respect to a specified batch value and an original input shape.

    Parameters
    ----------
    input_shape : tuple
        The input shape with batch axis unset.
    batch : int
        The batch value.

    Returns
    -------
    ishape : tuple
        The input shape with the value of batch axis equal to batch.
    """
    return [batch if s == -1 else s for s in input_shape]

def load_fname(prefix, suffix=None, with_ext=False):
    """Get the model files at a given stage.

    Parameters
    ----------
    prefix : string
        The file path without and extension.
    suffix : string
        The file suffix with respect to a given stage of MRT.
    with_ext: bool
        Whether to include ext file.

    Returns
    -------
    files : tuple of string
        The loaded file names.
    """
    suffix = "."+suffix if suffix is not None else ""
    return utils.extend_fname(prefix+suffix, with_ext)

def save_conf(fname, logger=logging, **conf_map):
    try:
        info_s = json.dumps(conf_map, indent=4)
    except:
        logger.error("Json seralize invalid with data: {}".format(conf_map))
        raise RuntimeError
    with open(fname, "w") as f:
        f.write(info_s)

def load_conf(fname, logger=logging):
    with open(fname, "r") as f:
        try:
            conf_map = json.load(f)
        except:
            logger.error("Json deserialize invalid, fname: {}".format(fname))
    return conf_map

def check_file_existance(*fpaths, logger=logging):
    for fpath in fpaths:
        if not path.exists(fpath):
            raise FileNotFoundError("fpath: {} does not exist".format(fpath))

def get_ctx(device_type, device_ids, dctx=default_ctx):
    if device_type is None:
        device_type = default_device_type
    if device_ids is None:
        device_ids = default_device_ids
    contex = dctx
    if device_type == "gpu":
        contex = mx.gpu(device_ids[0]) if len(device_ids) == 1 \
              else [mx.gpu(i) for i in device_ids]
    return contex

def mrt_prepare(
    model_dir, model_name, verbosity, device_type, device_ids, input_shape,
    split_keys):
    model_prefix = get_model_prefix(model_dir, model_name)
    logger = get_logger(verbosity)
    conf_prep_file = model_prefix + ".prepare.conf"
    conf_map = {}

    # preparation
    sym_path, prm_path = load_fname(model_prefix)
    if not path.exists(sym_path) or not path.exists(prm_path):
        save_model(
            model_name, data_dir=model_dir,
            ctx=get_ctx(device_type, device_ids))
    model = Model.load(sym_path, prm_path)
    model.prepare(set_batch(input_shape, 1))
    sym_prep_file, prm_prep_file = load_fname(
        model_prefix, suffix="prepare")
    model.save(sym_prep_file, prm_prep_file)
    conf_map["input_shape"] = input_shape
    save_conf(conf_prep_file, logger=logger, **conf_map)
    logger.info("preparation stage finihed")

    # model splitting
    if split_keys:
        sym_top_file, prm_top_file = load_fname(model_prefix, suffix='top')
        sym_base_file, prm_base_file = load_fname(
            model_prefix, suffix="base")
        base, top = model.split(split_keys)
        top.save(sym_top_file, prm_top_file)
        base.save(sym_base_file, prm_base_file)
        conf_map["split_keys"] = split_keys
        save_conf(conf_prep_file, logger=logger, **conf_map)
        logger.info("model splitting finished")
    else:
        logger.info("model splitting skipped")

def mrt_calibrate(
    model_dir, model_name, verbosity, dataset_name, dataset_dir,
    device_type, device_ids, calibrate_num, lambd, batch=default_batch):
    model_prefix = get_model_prefix(model_dir, model_name)
    logger = get_logger(verbosity)
    conf_prep_file = model_prefix + ".prepare.conf"
    check_file_existance(conf_prep_file, logger=logger)
    conf_map = load_conf(conf_prep_file, logger=logger)

    # calibration
    if conf_map.get("split_keys", "") == "":
        sym_prep_file, prm_prep_file = load_fname(
            model_prefix, suffix="prepare")
        check_file_existance(sym_prep_file, prm_prep_file, logger=logger)
        mrt = Model.load(sym_prep_file, prm_prep_file).get_mrt()
    else:
        sym_base_file, prm_base_file = load_fname(
            model_prefix, suffix="base")
        check_file_existance(sym_base_file, prm_base_file, logger=logger)
        mrt = Model.load(sym_base_file, prm_base_file).get_mrt()
    shp = set_batch(conf_map["input_shape"], batch)
    dataset = ds.DS_REG[dataset_name](shp, root=dataset_dir)
    data_iter_func = dataset.iter_func()
    if len(device_ids) > 1:
        raise RuntimeError(
            "device ids should be an integer in calibration stage")
    ctx = get_ctx(device_type, device_ids)
    for i in range(calibrate_num):
        data, _ = data_iter_func()
        mrt.set_data(data)
        mrt.calibrate(lambd=lambd, ctx=ctx)
    mrt.save(model_name+".mrt.calibrate", datadir=model_dir)
    conf_map["dataset_name"] = dataset_name
    save_conf(model_prefix+".calibrate.conf", logger=logger, **conf_map)
    logger.info("calibrate stage finished")

def mrt_quantize():
    pass
