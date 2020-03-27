from __future__ import print_function
from cvm import utils
from cvm.base import CVMContext, CPU, GPU, FORMAL
from cvm.dll import libcvm
import numpy as np
import os
import time

# model_root = "/data/std_out/resnet50_mxg"
# model_root = "/data/std_out/ssd_512_mobilenet1.0_coco_tfm/"
model_root = "/data/wlt/resnet18_v1_tfm"

CVMContext.set_global(GPU)

device_id = 0

graph_json, graph_params = utils.load_model(
    os.path.join(model_root, "symbol"),
    os.path.join(model_root, "params"))

lib = libcvm.CVM(graph_json, graph_params, device_id)

data_path = os.path.join(model_root, "data.npy")
input_data = utils.load_np_data(data_path)
## call inference

iter_num = 1
start = time.time()
for i in range(iter_num):
    infer_result = lib.Inference(input_data)
end = time.time()
print ("Infer Time: ", (end - start) * 1e3 / iter_num, " ms")

## compare result
# output_size = lib.GetOutputLength()
# output_path = model_root + "/result_0.npy"
# correct_data = np.load(output_path)
# for i in range(output_size):
#     assert(correct_data.flatten()[i] == infer_result[i])

print ("pass")

lib.FreeModel()
