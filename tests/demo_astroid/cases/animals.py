"""Animals and the sound they make."""


class Cat:  # inferred: ClassDef(animals.Cat)
    def speak(self) -> str:
        return "meow"  # inferred: Const('meow')


class Kitten(Cat):
    pass


Cat  # inferred: ClassDef(animals.Cat)
Cat()  # inferred: Instance(animals.Cat)
Cat().speak  # inferred: BoundMethod(animals.Cat.speak)
Cat().speak()  # inferred: Const('meow')
Kitten().speak()  # inferred-value: 'meow'
Kitten().purr  # inferred-type: InferenceError
