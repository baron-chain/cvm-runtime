import sys
from os import path
import argparse
from typing import Tuple, List, Union
import logging

import mxnet as mx

from mrt.conf import MRT_MODEL_ROOT, MRT_DATASET_ROOT
from mrt.common import cmd, log, thread
from mrt.transformer import Model
from mrt import utils
from mrt.gluon_zoo import save_model
from mrt import dataset as ds

# set up dependencies
__ROOT__ = path.dirname(path.realpath(__file__))
sys.path.insert(0, path.join(__ROOT__, "python"))

LOG_MSG = ",".join(["{}:{}".format(l, n) \
    for l, n in zip(log.LOG_LEVELS, log.LOG_NAMES)])

# @cmd.option("-v", "--verbosity", metavar="LEVEL",
            # choices=log.LOG_NAMES, default=log.level2name(log.DEBUG),
            # help="log verbosity to pring information, " + \
                # "available options: {}".format(log.LOG_NAMES) + \
                # " by default {}".format(log.level2name(log.DEBUG)))
# @cmd.global_options()
# def global_func(args):
    # log.Init(log.name2level(args.verbosity))

def get_ctx(device_type, device_ids, dctx=mx.cpu()):
    contex = dctx
    if device_type == 'gpu':
        contex = mx.gpu(device_ids[0]) if len(device_ids) == 1 \
              else [mx.gpu(i) for i in device_ids]
    return contex

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

# TODO: option string abbreviation
@cmd.option("--model-dir", type=str, default=MRT_MODEL_ROOT)
@cmd.option("model_name", type=str)
@cmd.option("--device-type-default", type=str, default="cpu",
            choices=["cpu", "gpu"])
@cmd.option("--device-ids-default", nargs="+", type=int, default=[0])
@cmd.option("--verbosity", type=str, default="debug",
            choices=["none", "debug", "info", "warning", "error", "critical"])
@cmd.option("--input-shape", nargs="+", type=int, default=[-1, 3, 224, 224])
@cmd.option("--start", type=str, default="default",
            choices=["default", "prepare", "split_model",
            "calibrate", "quantize", "merge_model"])
@cmd.option("--no-dump-prepare", action="store_false")
@cmd.option("--keys", nargs="+", type=str, default="")
@cmd.option("--no-dump-splitmodel", action="store_false")
@cmd.option("--batch-calibrate", type=int, default=16)
@cmd.option("--num-calibrate", type=int, default=1)
@cmd.option("--lambd", type=int)
@cmd.option("--dataset", type=str, default="imagenet",
            choices=list(ds.DS_REG.keys()))
@cmd.option("--dataset-dir", type=str, default=MRT_DATASET_ROOT)
@cmd.option("--device-type-calibrate", type=str, default="cpu",
            choices=["cpu", "gpu"])
@cmd.option("--device-ids-calibrate", nargs="+", type=int, default=[0])
@cmd.option("--no-dump-calibrate", action="store_false")
@cmd.module("", as_main=True,
            description="""
CVM Python Tool
""")
def cvm_main(args):
    # default
    log.Init(log.name2level(args.verbosity.upper()))
    logger = logging.getLogger("log.main")
    model_dir = args.model_dir
    if model_dir.startswith("~"):
        model_dir = path.expanduser(model_dir)
    assert path.exists(model_dir), \
        "Please create the folder `data` first"
    model_name = args.model_name
    model_prefix = path.join(model_dir, model_name)
    model_ctx = get_ctx(args.device_type_default, args.device_ids_default)
    input_shape = args.input_shape
    start_pos = {
        'default': 0, 'prepare': 1, 'split_model': 2,
        'calibration': 3, 'quantization': 4, 'merge_model': 5}
    start_point = start_pos[args.start]

    # prepare
    sym_file, prm_file = load_fname(model_prefix, suffix='prepare')
    sym_path, prm_path = load_fname(model_prefix)
    if not path.exists(sym_path) or not path.exists(prm_path):
        save_model(model_name, data_dir=model_dir, ctx=model_ctx)

    if start_point < 1:
        model = Model.load(sym_path, prm_path)
        model.prepare(set_batch(input_shape, 1))
        if not args.no_dump_prepare:
            model.save(sym_file, prm_file)
        logger.info("preparation stage finihed")
    elif start_point == 1:
        for fpath in [sym_file, prm_file]:
            if not path.exists(fpath):
                raise RuntimeError("file path {} not found".format(fpath))
        model = Model.load(sym_file, prm_file)
        logger.info("preparation stage checked")

    # split model
    sym_top_file, prm_top_file = load_fname(model_prefix, suffix='top')
    sym_base_file, prm_base_file = load_fname(model_prefix, suffix='base')
    keys = args.keys
    if keys == "":
        logger.info("model splitting stage skipped")
    elif start_point < 2:
        base, top = model.split(keys)
        if not args.no_dump_splitmodel:
            top.save(sym_top_file, prm_top_file)
            base.save(sym_base_file, prm_base_file)
        logger.info("model splitting stage finished")
    elif start_point == 2:
        for fpath in \
            [sym_top_file, prm_top_file, sym_base_file, prm_base_file]:
            if not path.exists(fpath):
                raise RuntimeError("file path {} not found".format(fpath))
        top = Model.load(sym_top_file, prm_top_file)
        base = Model.load(sym_base_file, prm_base_file)
        logger.info("model splitting stage checked")

    # calibrate
    model_name_calib = model_name + '.mrt.calibrate'
    batch = args.batch_calibrate
    ds_name = args.dataset
    if start_point < 3:
        mrt = model.get_mrt() if keys == '' else base.get_mrt()
        shp = set_batch(input_shape, batch)
        dataset = ds.DS_REG[ds_name](shp, root=args.dataset_dir)
        data_iter_func = dataset.iter_func()
        device_type_calibrate = args.device_type_calibrate
        device_ids_calibrate = args.device_ids_calibrate
        ctx = get_ctx(
            device_type_calibrate, device_ids_calibrate, dctx=model_ctx)
        for i in range(args.num_calibrate):
            data, _ = data_iter_func()
            mrt.set_data(data)
            mrt.calibrate(lambd=args.lambd, ctx=ctx)
        if not args.no_dump_calibrate:
            mrt.save(model_name_calib, datadir=model_dir)
        logger.info("calibrate stage finished")
    elif start_point == 3:
        fpaths = utils.extend_fname(model_prefix)
        for fpath in fpaths:
            if not path.exists(fpath):
                raise RuntimeError("file path {} not found".format(fpath))
        mrt = MRT.load(model_name_calib, datadir=model_dir)
        if keys != "":
            for fpath in [sym_top_file, prm_top_file]:
                if not path.exists(fpath):
                    raise RuntimeError("file path {} not found".format(fpath))
            top = Model.load(sym_top_file, prm_top_file)
        logger.info("calibration stage checkd")

    return
    # TODO(ryt), calibration, quantization, merge_model
    # quantization
    sec = 'QUANTIZATION'
    model_name_quant = model_name + '.mrt.quantize'
    if start_point < 4:
        restore_names = _get_val(
            cfg, sec, 'Restore_name', dtype=ARRAY(str_t), dval=[])
        name_to_op = {}
        from sym_utils import topo_sort
        for sym in topo_sort(mrt.current_model.symbol):
            name, op_name = sym.attr('name'), sym.attr('op_name')
            if op_name not in name_to_op:
                name_to_op[op_name] = []
            name_to_op[op_name].append(name)
        new_names = []
        for name in restore_names:
            if name.startswith("_OP_") and name[4:] in name_to_op:
                for new_name in name_to_op[name[4:]]:
                    new_names.append(new_name)
            else:
                new_names.append(name)
        restore_names = set(new_names)
        if '_ALL_EXCEPT_' in restore_names:
            from tfm_base import _pass_manager
            from tfm_ops import disabled_restore_ops

            quantize_ops = [op_name for op_name in _pass_manager["quantize"] \
                            if op_name not in disabled_restore_ops]
            restore_names_new = []
            for sym in topo_sort(mrt.current_model.symbol):
                name, op_name = sym.attr('name'), sym.attr('op_name')
                if op_name in quantize_ops and \
                    name not in restore_names:
                    restore_names_new.append(name)
            restore_names = set(restore_names_new)
        for name in restore_names:
            mrt.set_restore(name)
        input_precision = _get_val(
            cfg, sec, 'Input_precision', dtype=int_t, dval=None)
        if input_precision is not None:
            mrt.set_input_prec(input_precision)
        output_precision = _get_val(
            cfg, sec, 'Output_precision', dtype=int_t, dval=None)
        if output_precision is not None:
            mrt.set_output_prec(output_precision)
        ctx = _get_ctx(cfg, sec, dctx=model_ctx)
        softmax_lambd = _get_val(
            cfg, sec, 'Softmax_lambd', dtype=float_t, dval=None)
        if softmax_lambd is not None:
            mrt.set_softmax_lambd(softmax_lambd)
        shift_bits = _get_val(
            cfg, sec, 'Shift_bits', dtype=int_t, dval=None)
        if shift_bits is not None:
            mrt.set_shift_bits(shift_bits)
        thresholds = _get_val(
            cfg, sec, 'Thresholds', dtype=PAIR(str_t, float_t), dval=None)
        if thresholds is not None:
            for name, threshold in thresholds.items():
                mrt.set_threshold(name, threshold)
        mrt.quantize()
        inputs_ext = mrt.get_inputs_ext()
        dump = _get_val(cfg, sec, 'Dump', dtype=bool_t, dval=False)
        if dump:
            mrt.save(model_name_quant, datadir=model_dir)
            oscales = mrt.get_output_scales()
            inputs_ext = mrt.get_inputs_ext()
            infos = ['oscales: ', oscales,
                     'input_ext: ', inputs_ext,
                     'input shapes: ', input_shape]
            ext_all_file = path.join(model_dir, model_name+".all.quantize.ext")
            sim.save_ext(ext_all_file, *infos)
        logger.info("`%s` stage finished" % sec)
    elif start_point == 4:
        _checkpoint_exist(
            sec, *list(utils.extend_fname(
            model_prefix+'.mrt.quantize', with_ext=True)))
        mrt = MRT.load(model_name_quant, datadir=model_dir)
        inputs_ext = mrt.get_inputs_ext()
        dump = _get_val(cfg, sec, 'Dump', dtype=bool_t, dval=False)
        if keys != "":
            _checkpoint_exist(sec, sym_top_file, prm_top_file)
            top = Model.load(sym_top_file, prm_top_file)
        logger.info("`%s` stage checkd" % sec)

    # merge_model
    sec = 'MERGE_MODEL'
    sym_all_file, prm_all_file, ext_all_file = _load_fname(
        model_prefix, suffix='all.quantize', with_ext=True)
    if keys == '':
        _check(start_point != 5, 'DEFAULT', 'Start',
               message="Invalid start point")
        qmodel = mrt.current_model
        oscales = mrt.get_output_scales()
        logger.info("`%s` stage skipped" % sec)
    elif start_point < 5:
        qmodel = mrt.current_model
        mrt_oscales = mrt.get_output_scales()
        model_merger = Model.merger(qmodel, top, mrt.get_maps())
        attribute_deps = _get_val(
            cfg, sec, 'Attribute_deps', dtype=PAIR(str_t, str_t, str_t))

        name_idx = {mrt.get_maps().get(
            s.attr("name"), s.attr("name")): i \
            for i, s in enumerate(qmodel.symbol)}
        def mergefunc(node, params, graph):
            name, op_name = node.attr('name'), node.attr('op_name')
            childs, attr = sutils.sym_iter(
                node.get_children()), node.list_attr()
            if op_name in attribute_deps:
                attr_deps = attribute_deps[op_name]
                for attr_name, v in attr_deps.items():
                    val = sutils.get_attr(attr, attr_name, 0)
                    attr[attr_name] = int(val*mrt_oscales[name_idx[v]])
                node = sutils.get_mxnet_op(op_name)(
                    *childs, **attr, name=name)
            return node

        qmodel = model_merger.merge(callback=mergefunc)
        oscale_maps = _get_val(
            cfg, sec, 'Oscale_maps', dtype=PAIR(str_t, str_t))
        oscales = model_merger.get_output_scales(
            mrt_oscales, oscale_maps)
        inputs_ext = mrt.get_inputs_ext()
        dump = _get_val(cfg, sec, 'Dump', dtype=bool_t, dval=False)
        if dump:
            qmodel.save(sym_all_file, prm_all_file)
            infos = ['oscales: ', oscales,
                     'input_ext: ', inputs_ext,
                     'input shapes: ', input_shape]
            sim.save_ext(ext_all_file, *infos)
        logger.info("`%s` stage finished" % sec)
    else:
        _check(start_point == 5, 'DEFAULT', 'Start',
               message='Start_point invalid')
        qmodel = Model.load(sym_all_file, prm_all_file)
        _, oscales, _, inputs_ext, _, _ = sim.load_ext(ext_all_file)
        logger.info("`%s` stage checked" % sec)

    # evaluation
    sec = 'EVALUATION'
    if sec in cfg.sections():
        iter_num = _get_val(cfg, sec, 'Iter_num', dtype=int_t, dval=0)
        batch = _get_val(cfg, sec, 'Batch', dtype=int_t, dval=batch)
        ctx = _get_ctx(cfg, sec, dctx=model_ctx)
        if isinstance(ctx, mx.Context):
            ctx = [ctx]
        org_model = Model.load(sym_path, prm_path)
        graph = org_model.to_graph(ctx=ctx)
        dataset = ds.DS_REG[ds_name](set_batch(input_shape, batch))
        data_iter_func = dataset.iter_func()
        metric = dataset.metrics()

        baxis = batch_axis(input_shape)
        olen = len(org_model.symbol)
        def forward(net, data, ctx):
            """ Multiple xpu run support.
            """
            data = gluon.utils.split_and_load(
                data, ctx_list=ctx, batch_axis=baxis, even_split=False)
            outs = [net(d) for d in data]
            if olen == 1:
                outs = nd.concatenate(outs)
            else:
                outs = [nd.concatenate([outs[i][j] \
                    for i in range(len(outs))]) for j in range(olen)]
            return outs

        def evalfunc(data, label):
            outs = forward(graph, data, ctx=ctx)
            acc = dataset.validate(metric, outs, label)
            return acc

        ngpus = len(ctx)
        _check(
            not batch % ngpus, sec, 'Device_ids',
            'Batch must be divisible by the number of gpus')
        split_batch = batch//ngpus
        rqmodel = reduce_graph(qmodel, {
            'data': set_batch(input_shape, split_batch)})
        qgraph = rqmodel.to_graph(ctx=ctx)
        qmetric = dataset.metrics()

        def quantize(data, label):
            data = sim.load_real_data(data, 'data', inputs_ext)
            outs = forward(qgraph, data, ctx)
            outs = outs / oscales[0] if olen == 1 \
                else [(t / oscales[i]) for i, t in enumerate(outs)]
            acc = dataset.validate(qmetric, outs, label)
            return acc

        if iter_num > 0:
            logger.info("Validating...")
            utils.multi_validate(evalfunc, data_iter_func, quantize,
                                 iter_num=iter_num,
                                 logger=logging.getLogger('mrt.validate'),
                                 batch_size=batch)
            logger.info("`%s` stage finished" % sec)

    # compilation
    sec = 'COMPILATION'
    if sec in cfg.sections():
        dump_dir = _get_path(
            cfg, sec, 'Dump_dir', is_dir=True, dpath=model_dir)
        batch = _get_val(cfg, sec, 'Batch', dtype=int_t, dval=batch)
        device_type = _get_val(cfg, sec, 'Device_type', dval='cpu')
        device_ids = _get_val(
            cfg, sec, 'Device_ids',
            dtype=ARRAY(int_t), dval=0)
        model_name_tfm = model_name + "_cvm"
        qmodel.to_cvm(model_name_tfm, datadir=dump_dir,
                      input_shape=set_batch(input_shape, batch),
                      target=device_type, device_ids=device_ids)

        dataset = ds.DS_REG[ds_name](set_batch(input_shape, batch))
        dump_data, _ = dataset.iter_func()()
        dump_data = sim.load_real_data(
            dump_data.astype("float64"), 'data', mrt.get_inputs_ext())
        model_root = path.join(dump_dir, model_name_tfm)
        np.save(path.join(model_root, "data.npy"),
                dump_data.astype('int8').asnumpy())
        infos = {
            "inputs_ext": inputs_ext,
            "oscales": oscales,
            "input_shapes": input_shape,
        }
        sim.save_ext(path.join(model_root, "ext"), infos)
        logger.info("`%s` stage finished" % sec)

    # starting processes
    thread.start_services(args)

if __name__ == "__main__":
    logger = logging.getLogger("main")
    cmd.Run()
