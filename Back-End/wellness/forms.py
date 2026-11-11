from django.contrib.auth.forms import SetPasswordForm
from django.core.validators import MaxLengthValidator


class ResetPasswordForm(SetPasswordForm):
    """Keep reset passwords compatible with the API's 128-character limit."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('new_password1', 'new_password2'):
            self.fields[name].max_length = 128
            self.fields[name].validators.append(MaxLengthValidator(128))
            self.fields[name].widget.attrs['maxlength'] = 128
