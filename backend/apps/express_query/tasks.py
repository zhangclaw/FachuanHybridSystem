from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.express_query.models import ExpressCarrierType, ExpressQueryTask, ExpressQueryTaskStatus
from apps.express_query.services import TrackingExtractionService, build_tracking_pdf, query_express

logger = logging.getLogger("apps.express_query")

# 快递公司编码映射
_CARRIER_MAP: dict[str, str] = {
    ExpressCarrierType.SF: "SF",
    ExpressCarrierType.EMS: "EMS",
}


def execute_express_query_task(task_id: int) -> None:
    """执行快递查询任务（从文件识别运单号）"""
    logger.info("开始执行快递查询任务", extra={"task_id": task_id})

    try:
        task = ExpressQueryTask.objects.get(id=task_id)
    except ExpressQueryTask.DoesNotExist:
        logger.error("快递查询任务不存在", extra={"task_id": task_id})
        return

    task.status = ExpressQueryTaskStatus.OCR_PARSING
    task.started_at = timezone.now()
    task.error_message = ""
    task.save(update_fields=["status", "started_at", "error_message", "updated_at"])

    try:
        extraction_service = TrackingExtractionService()
        extraction = extraction_service.extract(Path(task.waybill_image.path))

        task.ocr_text = extraction.ocr_text
        task.carrier_type = extraction.carrier_type
        task.tracking_number = extraction.tracking_number

        # PDF 只用第一页做 OCR，截断多页 PDF 节省空间
        if task.waybill_image and (task.waybill_image.name or "").endswith(".pdf"):
            TrackingExtractionService.truncate_pdf_to_first_page(Path(task.waybill_image.path))

        if not extraction.tracking_number:
            raise ValueError("OCR 未识别到有效运单号")

        if extraction.carrier_type not in {"sf", "ems"}:
            raise ValueError("OCR 已识别运单号，但未能识别承运商（仅支持 EMS/顺丰）")

        task.status = ExpressQueryTaskStatus.QUERYING
        task.save(
            update_fields=[
                "ocr_text",
                "carrier_type",
                "tracking_number",
                "status",
                "updated_at",
            ]
        )

        _execute_api_query(task)

    except Exception as exc:
        logger.error("快递查询任务执行失败", extra={"task_id": task_id, "error": str(exc)}, exc_info=True)
        task.status = ExpressQueryTaskStatus.FAILED
        task.error_message = str(exc)
        task.finished_at = timezone.now()
        task.save(update_fields=["status", "error_message", "finished_at", "updated_at"])


def execute_manual_express_query_task(task_id: int) -> None:
    """执行手动输入的快递查询任务（跳过OCR）"""
    logger.info("开始执行手动输入快递查询任务", extra={"task_id": task_id})

    try:
        task = ExpressQueryTask.objects.get(id=task_id)
    except ExpressQueryTask.DoesNotExist:
        logger.error("快递查询任务不存在", extra={"task_id": task_id})
        return

    task.started_at = timezone.now()
    task.error_message = ""
    task.save(update_fields=["started_at", "error_message", "updated_at"])

    try:
        if not task.tracking_number:
            raise ValueError("缺少运单号")

        task.status = ExpressQueryTaskStatus.QUERYING
        task.save(update_fields=["status", "updated_at"])

        _execute_api_query(task)

    except Exception as exc:
        logger.error("手动输入快递查询任务执行失败", extra={"task_id": task_id, "error": str(exc)}, exc_info=True)
        task.status = ExpressQueryTaskStatus.FAILED
        task.error_message = str(exc)
        task.finished_at = timezone.now()
        task.save(update_fields=["status", "error_message", "finished_at", "updated_at"])


def _execute_api_query(task: ExpressQueryTask) -> None:
    """通过快递鸟 API 执行查询（替换原浏览器查询）。"""
    carrier_code = _CARRIER_MAP.get(task.carrier_type, "")

    result = query_express(
        tracking_number=task.tracking_number,
        carrier_code=carrier_code or None,
    )

    if not result.get("Success"):
        reason = result.get("Reason", "未知错误")
        raise ValueError(f"快递鸟查询失败: {reason}")

    # 更新承运商（API 可能自动识别）
    detected_carrier = result.get("ShipperCode", "")
    if detected_carrier:
        task.carrier_type = detected_carrier.lower()

    traces = result.get("Traces", [])
    state = result.get("State", "")

    # 生成 PDF
    output_rel_path = Path("express_query/results") / f"{task.id}_{task.carrier_type}_{task.tracking_number}.pdf"
    output_abs_path = Path(settings.MEDIA_ROOT) / output_rel_path

    build_tracking_pdf(
        output_path=output_abs_path,
        tracking_number=task.tracking_number,
        carrier_code=detected_carrier or task.carrier_type,
        traces=traces,
        state=state,
    )

    task.status = ExpressQueryTaskStatus.SUCCESS
    task.query_url = f"https://www.kdniao.com/query?nu={task.tracking_number}"
    task.result_pdf.name = output_rel_path.as_posix()
    task.result_payload = {
        "carrier_type": task.carrier_type,
        "tracking_number": task.tracking_number,
        "carrier_detected": detected_carrier,
        "state": state,
        "trace_count": len(traces),
        "pdf_path": output_rel_path.as_posix(),
    }
    task.finished_at = timezone.now()
    task.save(
        update_fields=[
            "status",
            "carrier_type",
            "query_url",
            "result_pdf",
            "result_payload",
            "finished_at",
            "updated_at",
        ]
    )
    logger.info("快递查询任务执行成功", extra={"task_id": task.id, "trace_count": len(traces)})
