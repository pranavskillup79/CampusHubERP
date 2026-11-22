# This descriptor stores a name after removing extra spaces at the ends.
class NameDescriptor:
    def __set_name__(self, owner, name):
        self.field_name = name
        self.private_name = "_" + name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__[self.private_name]

    def __set__(self, instance, value):
        if not isinstance(value, str):
            raise TypeError(f"{self.field_name} must be a string. Got {value!r}.")

        # Check the stripped name and keep the original value for the error.
        name = value.strip()
        if not name:
            raise ValueError(f"{self.field_name} cannot be empty. Got {value!r}.")
        instance.__dict__[self.private_name] = name


# This descriptor checks that an email address contains an @ sign.
class EmailDescriptor:
    def __set_name__(self, owner, name):
        self.field_name = name
        self.private_name = "_" + name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__[self.private_name]

    def __set__(self, instance, value):
        if not isinstance(value, str):
            raise TypeError(f"{self.field_name} must be a string. Got {value!r}.")
        if "@" not in value:
            raise ValueError(f"{self.field_name} must contain '@'. Got {value!r}.")
        instance.__dict__[self.private_name] = value


# This descriptor accepts whole-number ages from 16 to 80.
class AgeDescriptor:
    def __set_name__(self, owner, name):
        self.field_name = name
        self.private_name = "_" + name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__[self.private_name]

    def __set__(self, instance, value):
        # Python also treats True and False as integers, so reject them here.
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{self.field_name} must be an integer. Got {value!r}.")
        if value < 16 or value > 80:
            raise ValueError(f"{self.field_name} must be between 16 and 80. Got {value!r}.")
        instance.__dict__[self.private_name] = value
