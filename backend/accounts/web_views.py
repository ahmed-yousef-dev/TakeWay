"""
Web views for the out-of-app account deletion flow.
Used to satisfy Google Play's requirement for a web-based account deletion method.
"""

from django import forms
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from accounts.services import generate_otp, verify_deletion_otp, delete_account
from accounts.validators import validate_egyptian_phone


class AccountDeletionRequestForm(forms.Form):
    phone = forms.CharField(
        label=_("Phone Number"),
        max_length=15,
        validators=[validate_egyptian_phone],
        widget=forms.TextInput(attrs={"placeholder": "e.g. 01012345678", "class": "form-control"}),
    )

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            from accounts.validators import normalise_phone
            from accounts.models import User
            phone = normalise_phone(phone)
            if not User.objects.filter(phone=phone).exists():
                raise forms.ValidationError(_("No account is registered with this phone number."))
        return phone


class AccountDeletionConfirmForm(forms.Form):
    code = forms.CharField(
        label=_("OTP Code"),
        max_length=6,
        widget=forms.TextInput(attrs={"placeholder": "123456", "class": "form-control"}),
    )


class WebAccountDeletionRequestView(FormView):
    template_name = "accounts/delete_account.html"
    form_class = AccountDeletionRequestForm
    success_url = reverse_lazy("web-account-delete-confirm")

    def form_valid(self, form):
        phone = form.cleaned_data["phone"]
        try:
            generate_otp(phone)
            # Store phone in session for the next step
            self.request.session["delete_account_phone"] = phone
            return super().form_valid(form)
        except Exception:
            form.add_error(None, _("Could not generate OTP. Please try again."))
            return self.form_invalid(form)


class WebAccountDeletionConfirmView(FormView):
    template_name = "accounts/delete_account_confirm.html"
    form_class = AccountDeletionConfirmForm
    success_url = reverse_lazy("web-account-delete-success")

    def dispatch(self, request, *args, **kwargs):
        if "delete_account_phone" not in request.session:
            return redirect("web-account-delete-request")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["phone"] = self.request.session.get("delete_account_phone")
        return context

    def form_valid(self, form):
        phone = self.request.session.get("delete_account_phone")
        code = form.cleaned_data["code"]

        try:
            user = verify_deletion_otp(phone, code)
            delete_account(user)
            # Clear session
            del self.request.session["delete_account_phone"]
            return super().form_valid(form)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)


class WebAccountDeletionSuccessView(TemplateView):
    template_name = "accounts/delete_account_success.html"
