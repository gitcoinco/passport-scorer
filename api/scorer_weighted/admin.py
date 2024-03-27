from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin
from scorer_weighted.models import BinaryWeightedScorer, RescoreRequest, WeightedScorer
from django_ace import AceWidget
from django import forms

json_widget = AceWidget(
    mode="json",
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


class WeightedScorerForm(forms.ModelForm):
    class Meta:
        model = WeightedScorer
        widgets = {
            "weights": json_widget,
        }
        fields = "__all__"


@admin.register(WeightedScorer)
class WeightedScorerAdmin(ScorerModelAdmin):
    form = WeightedScorerForm
    list_display = ["id", "exclude_from_weight_updates"]
    list_filter = ["exclude_from_weight_updates"]


@admin.register(BinaryWeightedScorer)
class BinaryWeightedScorerAdmin(ScorerModelAdmin):
    form = WeightedScorerForm
    list_display = [
        "id",
        "threshold",
        "exclude_from_weight_updates",
    ]
    list_filter = ["exclude_from_weight_updates"]


@admin.register(RescoreRequest)
class RescoreRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "created_at",
        "status",
        "num_communities_requested",
        "num_communities_processed",
        "updated_at",
    ]
    list_filter = ["created_at", "status"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "num_communities_requested",
        "num_communities_processed",
        "status",
    ]
    search_fields = ["id"]
    ordering = ["-created_at"]
