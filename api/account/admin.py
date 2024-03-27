import boto3
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_ace import AceWidget
from rest_framework_api_key.admin import APIKeyAdmin
from scorer.scorer_admin import ScorerModelAdmin
from scorer_weighted.models import Scorer

from .models import Account, AccountAPIKey, Community, Customization


@admin.register(Account)
class AccountAdmin(ScorerModelAdmin):
    list_display = ("id", "address", "user")
    search_fields = ("address", "user__username")
    raw_id_fields = ("user",)


@admin.action(description="Recalculate scores", permissions=["change"])
def recalculate_scores(modeladmin, request, queryset):
    community_ids = [str(id) for id in queryset.values_list("id", flat=True)]

    # Create SQS client
    sqs = boto3.client("sqs", region_name="us-west-2")

    queue_url = settings.RESCORE_QUEUE_URL

    if queue_url == "":
        modeladmin.message_user(
            request,
            "Please set the RESCORE_QUEUE_URL environment variable to the URL of the SQS queue to use for rescoring.",
            level=messages.ERROR,
        )
        return

    # Send message to SQS queue
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageAttributes={
            "type": {"DataType": "String", "StringValue": "rescore"},
        },
        MessageBody=(",".join(community_ids)),
    )

    modeladmin.message_user(
        request,
        f"Submitted {len(community_ids)} communities for recalculation with message id {response['MessageId']}",
    )


@admin.register(Community)
class CommunityAdmin(ScorerModelAdmin):
    list_display = (
        "id",
        "name",
        "created_at",
        "description",
        "account",
        "scorer_link",
        "use_case",
        "deleted_at",
    )
    raw_id_fields = ("account", "scorer")
    search_fields = (
        "name",
        "description",
        "account__address",
        "created_at",
        "deleted_at",
    )
    readonly_fields = ("scorer_link",)
    actions = [recalculate_scores]

    def scorer_link(self, obj):
        # To add additional scorer types, just look at the URL on_delete
        # the edit page for the scorer type to get the category and field
        match obj.scorer.type:
            case Scorer.Type.WEIGHTED:
                category = "scorer_weighted"
                field = "weightedscorer"
            case Scorer.Type.WEIGHTED_BINARY | _:
                category = "scorer_weighted"
                field = "binaryweightedscorer"

        href = reverse(
            f"admin:{category}_{field}_change",
            args=[obj.get_scorer().pk],
        )
        return mark_safe(f'<a href="{href}">Scorer #{obj.scorer.id}</a>')

    scorer_link.short_description = "Scorer Link"


@admin.register(AccountAPIKey)
class AccountAPIKeyAdmin(APIKeyAdmin):
    raw_id_fields = ("account",)
    search_fields = (
        "id",
        "name",
        "prefix",
        "rate_limit",
        "account__user__username",
        "account__address",
    )

    list_display = (
        "name",
        "account",
        "rate_limit_display",
        "created",
        "revoked",
    )

    # Step 1: Define the edit action function
    def edit_selected(modeladmin, request, queryset):
        if queryset.count() != 1:
            modeladmin.message_user(
                request, "Please select exactly one row to edit.", level=messages.ERROR
            )
            return

        selected_instance = queryset.first()
        return HttpResponseRedirect(
            reverse(
                f"admin:{selected_instance._meta.app_label}_{selected_instance._meta.model_name}_change",
                args=(selected_instance.id,),
            )
        )

    # Step 3: Customize the action's display name in the dropdown menu
    edit_selected.short_description = "Edit selected row"

    # Step 2: Register the edit action
    actions = [edit_selected]


class APIKeyPermissionsAdmin(ScorerModelAdmin):
    list_display = ("id", "submit_passports", "read_scores", "create_scorers")


svg_widget = AceWidget(
    mode="svg",
    theme=None,  # try for example "twilight"
    wordwrap=False,
    width="500px",
    height="300px",
    minlines=None,
    maxlines=None,
    showprintmargin=True,
    showinvisibles=False,
    usesofttabs=True,
    tabsize=None,
    fontsize=None,
    toolbar=True,
    readonly=False,
    showgutter=True,  # To hide/show line numbers
    behaviours=True,  # To disable auto-append of quote when quotes are entered
)
xml_widget = AceWidget(
    mode="xml",
    theme=None,  # try for example "twilight"
    wordwrap=False,
    width="500px",
    height="300px",
    minlines=None,
    maxlines=None,
    showprintmargin=True,
    showinvisibles=False,
    usesofttabs=True,
    tabsize=None,
    fontsize=None,
    toolbar=True,
    readonly=False,
    showgutter=True,  # To hide/show line numbers
    behaviours=True,  # To disable auto-append of quote when quotes are entered
)


class CustomizationForm(forms.ModelForm):
    class Meta:
        model = Customization
        widgets = {
            "logo_image": svg_widget,
            # "logo_background": xml_widget,
            "logo_caption": xml_widget,
            "body_main_text": xml_widget,
            "body_sub_text": xml_widget,
        }
        fields = "__all__"


@admin.register(Customization)
class CustomizationAdmin(ScorerModelAdmin):
    form = CustomizationForm

    fieldsets = [
        (
            None,
            {
                "fields": ["path", "scorer"],
            },
        ),
        (
            "Colors",
            {
                "classes": ["collapse"],
                "fields": [
                    "customization_background_1",
                    "customization_background_2",
                    "customization_foreground_1",
                ],
            },
        ),
        (
            "Logo",
            {
                "classes": ["collapse"],
                "fields": ["logo_background", "logo_image", "logo_caption"],
            },
        ),
        (
            "Body",
            {
                "classes": ["collapse"],
                "fields": [
                    "body_action_text",
                    "body_action_url",
                    "body_main_text",
                    "body_sub_text",
                ],
            },
        ),
    ]

    list_display = ["id", "path"]
