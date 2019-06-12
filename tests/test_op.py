import mxnet as mx
from mxnet import ndarray as nd
import numpy as np
import json
def save_dict(params, fn):
    with open(fn, 'w+') as fout:
        fout.write("{")
        is_first = True
        for k, v in params.items():
            if is_first:
                is_first = False
            else:
                fout.write(", ")
            if k == 'step':
                k = 'stride'
            if k == 'axes':
                k = 'axis'
            fout.write("\"%s\": \"%s\"" % (k, v))
        fout.write("}\n")

def test_concatenate():
    print("test concatenate")
    shape = np.random.randint(low=1,high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/concatenate/in00.npy", a.astype("int32"));
    b = np.random.randint(low=-127, high=127, size=shape)#np.array([[1,2],[3,4]])
    np.save("/tmp/concatenate/in01.npy", b.astype("int32"));
    params = {'axis': 0}
    save_dict(params, "/tmp/concatenate/attr0.txt")
    c = np.concatenate((a,b), **params)
    np.save("/tmp/concatenate/out0.npy", c.astype("int32"));
    print(c.shape)

    shape = np.random.randint(low=1,high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/concatenate/in10.npy", a.astype("int32"));
    b = np.random.randint(low=-127, high=127, size=shape)#np.array([[1,2],[3,4]])
    np.save("/tmp/concatenate/in11.npy", b.astype("int32"));
    params = {'axis': 1}
    c = np.concatenate((a,b), **params)
    save_dict(params, "/tmp/concatenate/attr1.txt")
    np.save("/tmp/concatenate/out1.npy", c.astype("int32"));
    print(c.shape)

    shape = np.random.randint(low=1,high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/concatenate/in20.npy", a.astype("int32"));
    b = np.random.randint(low=-127, high=127, size=shape)#np.array([[1,2],[3,4]])
    np.save("/tmp/concatenate/in21.npy", b.astype("int32"));
    params = {'axis': 3}
    c = np.concatenate((a,b), **params)
    save_dict(params, "/tmp/concatenate/attr2.txt")
    np.save("/tmp/concatenate/out2.npy", c.astype("int32"));
    print(c.shape)

    shape = np.random.randint(low=1,high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/concatenate/in30.npy", a.astype("int32"));
    b = np.random.randint(low=-127, high=127, size=shape)#np.array([[1,2],[3,4]])
    np.save("/tmp/concatenate/in31.npy", b.astype("int32"));
    params = {'axis': -1}
    c = np.concatenate((a,b), **params)
    save_dict(params, "/tmp/concatenate/attr3.txt")
    np.save("/tmp/concatenate/out3.npy", c.astype("int32"));
    print(c.shape)

   # c = np.concatenate((a,b), axis=4)
   # np.save("/tmp/concatenate/out4.npy", c.astype("int32"));
   # print(c.shape)

def test_repeat():
    print("test repeat")

    shape = np.random.randint(low=1,high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/repeat/in00.npy", a.astype("int32"))
    params = {'axis':0, 'repeats':2}
    b = np.repeat(a,**params)
    save_dict(params, "/tmp/repeat/attr0.txt")
    np.save("/tmp/repeat/out0.npy", b.astype("int32"))
    print(b.shape)

    shape = np.random.randint(low=1,high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/repeat/in10.npy", a.astype("int32"))
    params = {'axis':1, 'repeats':3}
    b = np.repeat(a,**params)
    save_dict(params, "/tmp/repeat/attr1.txt")
    np.save("/tmp/repeat/out1.npy", b.astype("int32"))
    print(b.shape)

    shape = np.random.randint(low=1,high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/repeat/in20.npy", a.astype("int32"))
    params = {'axis':3, 'repeats':2}
    b = np.repeat(a,**params)
    save_dict(params, "/tmp/repeat/attr2.txt")
    np.save("/tmp/repeat/out2.npy", b.astype("int32"))
    print(b.shape)

    shape = np.random.randint(low=2,high=5, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    print(a)
    np.save("/tmp/repeat/in30.npy", a.astype("int32"))
    params = {'axis':-1, 'repeats':3}
    b = np.repeat(a,**params)
    save_dict(params, "/tmp/repeat/attr3.txt")
    np.save("/tmp/repeat/out3.npy", b.astype("int32"))
    print(b.shape)

def test_tile():
    print("test tile")
    shape = np.random.randint(low=1, high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/tile/in00.npy", a.astype("int32"))
    params = {'reps':[2]}
    save_dict(params, "/tmp/tile/attr0.txt")
    b = np.tile(a, **params)
    np.save("/tmp/tile/out0.npy", b.astype("int32"))
    print(b.shape)

    shape = np.random.randint(low=1, high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/tile/in10.npy", a.astype("int32"))
    params = {'reps':[2, 3]}
    save_dict(params, "/tmp/tile/attr1.txt")
    b = np.tile(a, **params)
    np.save("/tmp/tile/out1.npy", b.astype("int32"))
    print(b.shape)

    shape = np.random.randint(low=1, high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/tile/in20.npy", a.astype("int32"))
    params = {'reps':[2, 3, 1]}
    save_dict(params, "/tmp/tile/attr2.txt")
    b = np.tile(a, **params)
    np.save("/tmp/tile/out2.npy", b.astype("int32"))
    print(b.shape)

    shape = np.random.randint(low=1, high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/tile/in30.npy", a.astype("int32"))
    params = {'reps':[2, 3, 1, 4]}
    save_dict(params, "/tmp/tile/attr3.txt")
    b = np.tile(a, **params)
    np.save("/tmp/tile/out3.npy", b.astype("int32"))
    print(b.shape)

    shape = np.random.randint(low=1, high=100, size=(4)).astype("int32")
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/tile/in40.npy", a.astype("int32"))
    params = {'reps':[2, 3, 1, 4, 5]}
    save_dict(params, "/tmp/tile/attr4.txt")
    b = np.tile(a, **params)
    np.save("/tmp/tile/out4.npy", b.astype("int32"))
    print(b.shape)

def test_transpose():
    print("test transpose")
    shape = np.random.randint(low=1, high=5, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/transpose/in00.npy", a.astype("int32"))
    params = {'axes':[0,1,2,3]}
    save_dict(params, "/tmp/transpose/attr0.txt");
    b = np.transpose(a, **params)
    print(b.shape)
    np.save("/tmp/transpose/out0.npy", b.astype("int32"))

    shape = np.random.randint(low=1, high=5, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/transpose/in10.npy", a.astype("int32"))
    params = {'axes':[1,0,2,3]}
    save_dict(params, "/tmp/transpose/attr1.txt");
    b = np.transpose(a, **params)
    print(b.shape)
    np.save("/tmp/transpose/out1.npy", b.astype("int32"))

    shape = np.random.randint(low=1, high=5, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/transpose/in20.npy", a.astype("int32"))
    params = {'axes':[1,2,0,3]}
    save_dict(params, "/tmp/transpose/attr2.txt");
    b = np.transpose(a, **params)
    print(b.shape)
    np.save("/tmp/transpose/out2.npy", b.astype("int32"))

    shape = np.random.randint(low=1, high=5, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/transpose/in30.npy", a.astype("int32"))
    params = {'axes':[3,1,2,0]}
    save_dict(params, "/tmp/transpose/attr3.txt");
    b = np.transpose(a, **params)
    print(b.shape)
    np.save("/tmp/transpose/out3.npy", b.astype("int32"))

    shape = np.random.randint(low=1, high=5, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/transpose/in40.npy", a.astype("int32"))
    params = {}
    save_dict(params, "/tmp/transpose/attr4.txt");
    b = np.transpose(a, **params)
    print(b.shape)
    np.save("/tmp/transpose/out4.npy", b.astype("int32"))
    print(b.flatten())

def test_strided_slice():
    print("test strided slice")
    shape = np.random.randint(low=3, high=4, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    print(a)
    np.save("/tmp/strided_slice/in00.npy", a.astype("int32"))
    params = {"begin":[2,0], "end":[0,3], "step":[-1,2]}
    save_dict(params, "/tmp/strided_slice/attr0.txt")
    b = nd.slice(nd.array(a), **params)
    np.save("/tmp/strided_slice/out0.npy", b.asnumpy().astype("int32"))
    print(b.shape)
    print(b)

    shape = np.random.randint(low=3, high=4, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    print(a)
    np.save("/tmp/strided_slice/in10.npy", a.astype("int32"))
    params = {"begin":[0,0], "end":[2,3]}
    save_dict(params, "/tmp/strided_slice/attr1.txt")
    b = nd.slice(nd.array(a), **params)
    np.save("/tmp/strided_slice/out1.npy", b.asnumpy().astype("int32"))
    print(b.shape)

    shape = np.random.randint(low=3, high=4, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    print(a)
    np.save("/tmp/strided_slice/in20.npy", a.astype("int32"))
    params = {"begin":[0,0,1,1], "end":[1,2,3,3]}
    save_dict(params, "/tmp/strided_slice/attr2.txt")
    b = nd.slice(nd.array(a), **params)
    np.save("/tmp/strided_slice/out2.npy", b.asnumpy().astype("int32"))
    print(b.shape)

def test_slice_like():
    print("test slice like")
    shape = np.random.randint(low=5, high=10, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/slice_like/in00.npy", a.astype("int32"))
    b = np.zeros((4,4,4))
    np.save("/tmp/slice_like/in01.npy", b.astype("int32"))
    params = {'axes': [2,1]}
    save_dict(params, "/tmp/slice_like/attr0.txt")
    c = nd.slice_like(nd.array(a), nd.array(b), **params)
    np.save("/tmp/slice_like/out0.npy", b.astype("int32"))
    print(c.shape)

    shape = np.random.randint(low=5, high=10, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/slice_like/in10.npy", a.astype("int32"))
    b = np.zeros((4,4,4))
    np.save("/tmp/slice_like/in11.npy", b.astype("int32"))
    params = {'axes': [0]}
    save_dict(params, "/tmp/slice_like/attr1.txt")
    c = nd.slice_like(nd.array(a), nd.array(b), **params)
    np.save("/tmp/slice_like/out1.npy", b.astype("int32"))
    print(c.shape)

    shape = np.random.randint(low=5, high=10, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/slice_like/in20.npy", a.astype("int32"))
    b = np.zeros((4,4,4))
    np.save("/tmp/slice_like/in21.npy", b.astype("int32"))
    params = {'axes': [1,2]}
    save_dict(params, "/tmp/slice_like/attr2.txt")
    c = nd.slice_like(nd.array(a), nd.array(b), **params)
    np.save("/tmp/slice_like/out2.npy", b.astype("int32"))
    print(c.shape)

def test_get_valid_counts():
    print("test get_valid_counts")

def test_non_max_suppression():
    print("test non_max_suppression")

def test_take():
    print("test take")
    shape = np.random.randint(low=4, high=10, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/take/in00.npy", a.astype("int32"))
    indices = [[0,1],[2,3]]
    np.save("/tmp/take/in01.npy", np.array(indices).astype("int32"))
    params = {}
    save_dict(params, "/tmp/take/attr0.txt")
    c = np.take(a, indices, **params)
    np.save("/tmp/take/out0.npy", c.astype("int32"))
    print(c.shape)

    shape = np.random.randint(low=4, high=10, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/take/in10.npy", a.astype("int32"))
    indices = [0]
    np.save("/tmp/take/in11.npy", np.array(indices).astype("int32"))
    params = {}
    save_dict(params, "/tmp/take/attr1.txt")
    c = np.take(a, indices, **params)
    np.save("/tmp/take/out1.npy", c.astype("int32"))
    print(c.shape)

def test_max_pool():
    print("test max pool")


def test_cvm_lut():
    print("test cvm_lut")

def test_upsampling():
    print("test upsampling")

def test_squeeze():
    print("test squeeze")

def test_expand_dims():
    print("test expand dims")

def test_negative():
    print("test negative")

def test_max():
    print("test max")
    shape = np.random.randint(low=2, high=10, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/max/in0.npy", a.astype("int32"))
    params = {'axis':[1,3]}
    save_dict(params, "/tmp/max/attr0.txt")
    b = nd.max(nd.array(a), **params)
    np.save("/tmp/max/out0.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {}
    save_dict(params, "/tmp/max/attr1.txt")
    b = nd.max(nd.array(a), **params)
    np.save("/tmp/max/out1.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[0]}
    save_dict(params, "/tmp/max/attr2.txt")
    b = nd.max(nd.array(a), **params)
    np.save("/tmp/max/out2.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[2]}
    save_dict(params, "/tmp/max/attr3.txt")
    b = nd.max(nd.array(a), **params)
    np.save("/tmp/max/out3.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[3]}
    save_dict(params, "/tmp/max/attr4.txt")
    b = nd.max(nd.array(a), **params)
    np.save("/tmp/max/out4.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[1,2,3]}
    save_dict(params, "/tmp/max/attr5.txt")
    b = nd.max(nd.array(a), **params)
    np.save("/tmp/max/out5.npy", b.asnumpy().astype("int32"))
#   print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[0,1,2,3]}
    save_dict(params, "/tmp/max/attr6.txt")
    b = nd.max(nd.array(a), **params)
    np.save("/tmp/max/out6.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

def test_sum():
    print("test sum")
    shape = np.random.randint(low=2, high=10, size=(4))
    print(shape)
    a = np.random.randint(low=-127, high=127, size=shape)
    np.save("/tmp/sum/in0.npy", a.astype("int32"))
    params = {'axis':[1,3]}
    save_dict(params, "/tmp/sum/attr0.txt")
    b = nd.sum(nd.array(a), **params)
    np.save("/tmp/sum/out0.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {}
    save_dict(params, "/tmp/sum/attr1.txt")
    b = nd.sum(nd.array(a), **params)
    np.save("/tmp/sum/out1.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[0]}
    save_dict(params, "/tmp/sum/attr2.txt")
    b = nd.sum(nd.array(a), **params)
    np.save("/tmp/sum/out2.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[2]}
    save_dict(params, "/tmp/sum/attr3.txt")
    b = nd.sum(nd.array(a), **params)
    np.save("/tmp/sum/out3.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[3]}
    save_dict(params, "/tmp/sum/attr4.txt")
    b = nd.sum(nd.array(a), **params)
    np.save("/tmp/sum/out4.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[1,2,3]}
    save_dict(params, "/tmp/sum/attr5.txt")
    b = nd.sum(nd.array(a), **params)
    np.save("/tmp/sum/out5.npy", b.asnumpy().astype("int32"))
#   print(b.asnumpy().astype("int32").flatten())

    params = {'axis':[0,1,2,3]}
    save_dict(params, "/tmp/sum/attr6.txt")
    b = nd.sum(nd.array(a), **params)
    np.save("/tmp/sum/out6.npy", b.asnumpy().astype("int32"))
#    print(b.asnumpy().astype("int32").flatten())

#test_concatenate()
#test_repeat()
#test_tile()
#test_transpose()
#test_strided_slice()
#test_slice_like()
#test_take()
#test_max()
#test_sum()
