"""
Web views for the out-of-app account deletion flow.
Used to satisfy Google Play's requirement for a web-based account deletion method.
"""

from django import forms
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from accounts.services import generate_otp, verify_deletion_otp, delete_account, check_rate_limit
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
        
        # Apply rate limiting with exponential backoff (max 3 requests per 5 mins)
        throttle_key = f"web_otp_request_{phone}"
        allowed, wait_seconds = check_rate_limit(throttle_key, max_attempts=3, base_timeout=300)
        if not allowed:
            mins, secs = divmod(wait_seconds, 60)
            wait_str = f"{mins}m {secs}s" if mins else f"{secs}s"
            form.add_error(None, _(f"Too many requests. Please try again in {wait_str}."))
            form.retry_after = wait_seconds
            return self.form_invalid(form)

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

    def post(self, request, *args, **kwargs):
        if "confirm_delete" in request.POST:
            user_id = request.session.get("verified_user_id")
            if not user_id:
                return redirect("web-account-delete-request")
            
            from accounts.models import User
            try:
                user = User.objects.get(id=user_id)
                delete_account(user)
            except User.DoesNotExist:
                pass
                
            request.session.pop("delete_account_phone", None)
            request.session.pop("verified_user_id", None)
            return redirect(self.success_url)
            
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        phone = self.request.session.get("delete_account_phone")
        code = form.cleaned_data["code"]

        # Prevent brute-forcing the OTP (max 5 attempts)
        throttle_key = f"web_otp_verify_{phone}"
        allowed, wait_seconds = check_rate_limit(throttle_key, max_attempts=5, base_timeout=300)
        if not allowed:
            mins, secs = divmod(wait_seconds, 60)
            wait_str = f"{mins}m {secs}s" if mins else f"{secs}s"
            form.add_error(None, _(f"Too many failed attempts. Please try again in {wait_str}."))
            form.retry_after = wait_seconds
            return self.form_invalid(form)

        try:
            user = verify_deletion_otp(phone, code)
            # Set flag in session to indicate OTP is verified and user can be deleted
            self.request.session["verified_user_id"] = user.id
            return self.render_to_response(self.get_context_data(form=form, show_final_modal=True))
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)


class WebAccountDeletionSuccessView(TemplateView):
    template_name = "accounts/delete_account_success.html"
