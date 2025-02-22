import datetime
from typing import List, Dict, Tuple, Union, Optional

from db import enums
from .checks import check_argument_allowed, run_checks, run_limit_checks
from db.models import UploadTask, Attribute
import pandas as pd
from util.notification import create_notification
from db.enums import NotificationType
import os
import logging
import traceback
from db.business_objects import export

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_upload_task_message(
    task: UploadTask,
    include_duration: Optional[bool] = True,
    additional_information: str = "",
) -> str:
    message = f"Upload Task. ID: {task.id} Project ID: {task.project_id}. State: {task.state}. Progress: {task.progress}. Started at: {task.started_at}."
    message = (
        message + f"Finished at: {task.finished_at}." if task.finished_at else message
    )
    message = (
        message + f"Duration: {datetime.datetime.now() - task.started_at}."
        if include_duration
        else message
    )
    message = (
        f"{message} {additional_information}"
        if additional_information != ""
        else message
    )
    return message


def convert_to_record_dict(
    file_type: str,
    file_name: str,
    user_id: str,
    file_import_options: str,
    project_id: str,
) -> List:
    if not file_type:
        create_notification(
            NotificationType.FILE_TYPE_NOT_GIVEN,
            user_id,
            project_id,
        )

        if os.path.exists(file_name):
            os.remove(file_name)
        raise Exception("Upload conversion error", "Upload ran into errors")
    file_type = file_type.lower()
    if file_type in ["xls", "xlsm", "xlsb", "odf", "ods", "odt"]:
        file_type = "xlsx"

    file_import_options = (
        string_to_import_option_dict(file_import_options, user_id, project_id)
        if file_import_options
        else {}
    )
    try:
        if file_type in ["csv", "txt", "text"]:
            df = pd.read_csv(file_name, **file_import_options)
        elif file_type == "xlsx":
            df = pd.read_excel(file_name, **file_import_options)
        elif file_type == "html":
            df = pd.read_html(file_name, **file_import_options)
        elif file_type == "json":
            df = pd.read_json(file_name, **file_import_options)
        else:
            create_notification(
                NotificationType.INVALID_FILE_TYPE,
                user_id,
                project_id,
                file_type,
            )
            raise Exception("Upload conversion error", "Upload ran into errors")
        # ensure useable columns dont break the import
        df.fillna(" ", inplace=True)
    except Exception as e:
        logger.error(traceback.format_exc())
        create_notification(
            NotificationType.UPLOAD_CONVERSION_FAILED,
            user_id,
            project_id,
            str(e),
        )
        if os.path.exists(file_name):
            os.remove(file_name)
        raise Exception("Upload conversion error", "Upload ran into errors")
    if os.path.exists(file_name):
        os.remove(file_name)
    run_limit_checks(df, project_id, user_id)
    run_checks(df, project_id, user_id)
    return df.to_dict(orient="records")


def string_to_import_option_dict(
    import_string: str, user_id: str, project_id: str
) -> Dict[str, Union[str, int]]:
    splitted = import_string.split("\n")
    import_options = {}
    for e in splitted:
        tmp = e.split("=")
        if len(tmp) == 2:
            parameter = tmp[0].strip()
            if not check_argument_allowed(parameter):
                create_notification(
                    NotificationType.UNKNOWN_PARAMETER,
                    user_id,
                    project_id,
                    parameter,
                )
            else:
                import_options[parameter] = tmp[1].strip()
                if import_options[parameter].isdigit():
                    import_options[parameter] = int(import_options[parameter])
    return import_options


def infer_attribute(key: str) -> str:
    seperator_idx = key.find("__")
    return key[:seperator_idx] if seperator_idx != -1 else key
