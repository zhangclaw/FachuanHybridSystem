"""案件组 - 关联同一纠纷的不同阶段案件（一审/二审/再审等）"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager

    from .case import Case


class CaseGroup(models.Model):
    """将同一纠纷的多个案件关联在一起，形成时间线。"""

    id: int
    name = models.CharField(max_length=200, verbose_name=_("案件组名称"))
    note = models.TextField(blank=True, default="", verbose_name=_("备注"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("创建时间"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("更新时间"))

    if TYPE_CHECKING:
        cases: RelatedManager[Case]

    class Meta:
        verbose_name = _("案件组")
        verbose_name_plural = _("案件组")
        ordering: ClassVar = ["-created_at"]

    def __str__(self) -> str:
        return self.name
