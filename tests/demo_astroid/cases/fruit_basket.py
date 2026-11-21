"""Counting the fruits of a basket."""

apples = 2  # inferred: Const(2)
bananas = 3
apples + bananas  # inferred: Const(5)
"apple" + " pie"  # inferred-value: 'apple pie'
[apples, bananas]  # inferred-type: List
(apples, bananas)  # inferred: Tuple((apples, bananas))
{"apple": apples}  # inferred-type: Dict
apples > bananas  # inferred-type: Const  # inferred-value: False
len("banana")  # inferred: Const(6)
cherries  # inferred: InferenceError
bananas if apples else "kiwi"  # inferred: Const(3)
