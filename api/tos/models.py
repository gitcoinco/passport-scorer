"""Tos Models"""

from account.models import EthAddressField, EthSignature, Nonce, NonceField
from django.db import models
from django.db.models import Q, UniqueConstraint
from eth_account import Account
from eth_account.messages import encode_defunct


class Tos(models.Model):
    class TosType(models.TextChoices):
        IDENTITY_STAKING = "IST"

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    type = models.CharField(
        max_length=3, choices=TosType.choices, blank=False, db_index=True
    )
    active = models.BooleanField(
        default=False,
        help_text="Only 1 active tos is alloed per type. The active is the one that will be required for users to approve",
    )
    final = models.BooleanField(
        default=False,
        help_text="Once an object is made final, it cannot be edited any more. This is to prevent from editing TOS that might have been accepted by users.",
    )
    content = models.TextField(blank=False, null=False)

    def __str__(self):
        return f"Tos #{self.id} for type({self.type}) - active({self.active})"

    def get_message_for_nonce(self, nonce: str) -> str:
        return f"{self.content}\n\nNonce: {nonce}"

    @classmethod
    def get_message_with_nonce(cls, type: str) -> tuple[str, str]:
        tos = Tos.objects.get(type=type, active=True, final=True)
        nonce = Nonce.create_nonce()
        return tos.get_message_for_nonce(nonce.nonce), nonce.nonce

    @classmethod
    def accept(cls, type: str, nonce: str, signature: str) -> bool:
        if Nonce.use_nonce(nonce):
            tos = Tos.objects.get(type=type, active=True, final=True)
            encoded_message = encode_defunct(text=tos.get_message_for_nonce(nonce))
            address = Account.recover_message(
                encoded_message,
                signature=signature,
            )

            TosAcceptanceProof(
                address=address, signature=signature, nonce=nonce, tos=tos
            ).save()
            return True
        return False

    def has_any_accepted(self) -> bool:
        return self.acceptance_proofs.exists()

    class Meta:
        constraints = [
            # Ensure only 1 active object at 1 time
            UniqueConstraint(
                fields=["type", "final", "active"],
                name="Only 1 active final tos is allowed for any given type",
                condition=Q(final=True, active=True),
            ),
        ]


class TosAcceptanceProof(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    tos = models.ForeignKey(
        Tos, related_name="acceptance_proofs", on_delete=models.PROTECT
    )
    address = EthAddressField(null=False, blank=False)
    signature = EthSignature(null=False, blank=False)
    nonce = NonceField(unique=True, null=False, blank=False)

    def __str__(self):
        return f"Proof for tos #{self.tos_id} - {self.address} - {self.nonce} - {self.signature}"

    @classmethod
    def has_accepted(cls, address: str, tos_type: str) -> bool:
        try:
            ret = TosAcceptanceProof.objects.filter(
                address=address.lower(), tos__type=tos_type, tos__active=True
            ).exists()
            return ret
        except Exception:
            raise

    class Meta:
        unique_together = ["tos", "address"]
