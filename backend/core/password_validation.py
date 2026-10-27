from django.core.exceptions import ValidationError


class NonBlankPasswordValidator:
    def validate(self, password, user=None):
        if not password.strip():
            raise ValidationError('Your password cannot consist only of whitespace.', code='password_blank')

    def get_help_text(self):
        return 'Your password must contain a non-whitespace character.'
