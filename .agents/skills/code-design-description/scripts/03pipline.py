from lazyllm import pipeline,parallel

class Functor(object):
    def __call__(self, x): return x * x

def f1(input, input2=0): return input + input2 + 1
def f2(input): return input + 3
def f3(input): return f'f3-{input}'
def f4(in1, in2, in3): return f'get [{in1}], [{in2}], [{in3}]'



# pipline顺序执行所有函数，后函数的输入是前函数输出
# pipline的call函数是为每个输入带入call的值作为传入参数
# assert pipeline(f1, f2, f3, Functor)(1) == 256

print(pipeline(f1)(2))

# pipline函数注册（给函数加一个component装饰器）

# 另一种调用
# 参数绑定
# bind函数位于builtins，可以直接调
# p.f4 = f4 | bind(p.input, _0, p.f2)   也行
# pipline().bind()  给pipline绑数据
from lazyllm import pipeline, _0
with pipeline() as p:
    p.f1 = f1
    p.f2 = f2
    p.f3 = f3
    p.f4 = bind(f4, p.input, _0, p.f2)
# assert p(1) == 'get [1], [f3-5], [5]'
print(p(1))


# parallel  并发执行，x个函数x个输出
# 可以进行后处理：可以对结果求和，转格式等..  ；  标准输出是一个
with parallel() as f:
    f.f1=f1
    f.f2=f2
print(f(1))

# 可顺序执行，非并发执行 .sequential

# parallel高端用法：barrier  类比任务表的重点任务，大家都要走到这个任务才能向下走，避免某个任务执行过慢占用gpu
