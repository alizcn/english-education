from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class SignupForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label=_('E-posta'),
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),
    )
    kvkk_consent = forms.BooleanField(
        required=True,
        label=_('KVKK Aydınlatma Metnini okudum ve onaylıyorum.'),
        error_messages={'required': _('Devam etmek için KVKK metnini onaylamalısın.')},
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            raise ValidationError(_('E-posta zorunludur.'))
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError(_('Bu e-posta başka bir hesapta kullanılıyor.'))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': _('Ad'),
            'last_name': _('Soyad'),
            'email': _('E-posta'),
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            return email
        qs = get_user_model().objects.exclude(pk=self.instance.pk).filter(email__iexact=email)
        if qs.exists():
            raise ValidationError(_('Bu e-posta başka bir hesapta kullanılıyor.'))
        return email
