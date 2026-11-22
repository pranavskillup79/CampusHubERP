from abc import ABCMeta
from datetime import datetime


# This metaclass tracks when each object is created and edited.
class AuditMeta(ABCMeta):
    def __new__(metaclass, name, bases, namespace):
        # Install a setter that records the time after a successful edit.
        def set_attribute(instance, attribute, value):
            object.__setattr__(instance, attribute, value)

            # Skip timestamp fields and wait until the object is initialized.
            if attribute == "created_at" or attribute == "updated_at":
                return
            if "created_at" in instance.__dict__:
                instance.updated_at = datetime.now()

        namespace["__setattr__"] = set_attribute
        return super().__new__(metaclass, name, bases, namespace)

    def __call__(cls, *args, **kwargs):
        # Use the same starting time for both fields after initialization.
        instance = super().__call__(*args, **kwargs)
        current_time = datetime.now()
        instance.created_at = current_time
        instance.updated_at = current_time
        return instance
