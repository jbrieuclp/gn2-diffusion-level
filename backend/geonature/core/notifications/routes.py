import json

import time
import logging

from flask import (
    Blueprint,
    request,
    Response,
    current_app,
    send_from_directory,
    render_template,
    jsonify,
    g,
)
from werkzeug.exceptions import Forbidden, BadRequest
from sqlalchemy import distinct, func, desc, asc, select, text, update
import sqlalchemy as sa
from sqlalchemy.orm import joinedload

from utils_flask_sqla.generic import serializeQuery, GenericTable
from utils_flask_sqla.response import to_csv_resp, to_json_resp, json_resp

from geonature.utils import filemanager
from geonature.utils.env import DB
from geonature.utils.errors import GeonatureApiError

from pypnusershub.db.tools import user_from_token
from pypnusershub.db.models import User

from geonature.core.gn_permissions import decorators as permissions
from geonature.core.notifications.models import (
    TNotifications,
    BibNotificationsMethods,
    BibNotificationsStatus,
    TNotificationsRules,
    BibNotificationsTemplates,
    BibNotificationsCategories,
)
from geonature.core.notifications.utils import Notification

routes = Blueprint("notifications", __name__)
log = logging.getLogger()

# Notification input in Json
# Mandatory attribut (category, method)
# reserved attribut (title, url, content)
# if attribut content exist no templating
# otherwise all other attribut will be used in templating
@routes.route("/notification", methods=["PUT"])
@permissions.login_required
def create_notification_from_api():

    requestData = request.get_json()
    if requestData is None:
        raise BadRequest("Empty request data")

    Notification.create_notification(requestData)


# Get all database notification for current user
@routes.route("/notifications", methods=["GET"])
@permissions.login_required
def list_database_notification():

    notifications = TNotifications.query.filter(TNotifications.id_role == g.current_user.id_role)
    notifications = notifications.order_by(
        TNotifications.code_status.desc(), TNotifications.creation_date.desc()
    )
    notifications = notifications.options(joinedload("notification_status"))
    result = [
        notificationsResult.as_dict(
            fields=[
                "id_notification",
                "id_role",
                "title",
                "content",
                "url",
                "code_status",
                "creation_date",
                "notification_status.code_notification_status",
                "notification_status.label_notification_status",
            ]
        )
        for notificationsResult in notifications.all()
    ]
    return jsonify(result)


# count database unread notification for current user
@routes.route("/count", methods=["GET"])
@permissions.login_required
def count_notification():

    notificationNumber = TNotifications.query.filter(
        TNotifications.id_role == g.current_user.id_role, TNotifications.code_status == "UNREAD"
    ).count()
    return jsonify(notificationNumber)


# Update status ( for the moment only UNREAD/READ)
@routes.route("/notification", methods=["POST"])
@permissions.login_required
def update_notification():

    data = request.get_json()
    if data is None:
        raise BadRequest("Empty request data")

    # Information to check if notification is need
    id_notification = data["id_notification"]
    notification = TNotifications.query.get_or_404(id_notification)
    if notification.id_role != g.current_user.id_role:
        raise Forbidden
    notification.code_status = "READ"
    DB.session.commit()


# Get all database notification for current user
@routes.route("/rules", methods=["GET"])
@permissions.login_required
def list_notification_rules():

    notificationsRules = TNotificationsRules.query.filter(
        TNotificationsRules.id_role == g.current_user.id_role
    )
    notificationsRules = notificationsRules.order_by(
        TNotificationsRules.code_notification_category.desc(),
        TNotificationsRules.code_notification_method.desc(),
    )
    notificationsRules = notificationsRules.options(joinedload("notification_method"))
    notificationsRules = notificationsRules.options(joinedload("notification_category"))

    result = [
        notificationsRulesResult.as_dict(
            fields=[
                "id_notification_rules",
                "id_role",
                "code_notification_method",
                "code_notification_category",
                "notification_method.label_notification_method",
                "notification_method.description_notification_method",
                "notification_category.label_notification_category",
                "notification_category.description_notification_category",
            ]
        )
        for notificationsRulesResult in notificationsRules.all()
    ]
    return jsonify(result)


# add rule for user
@routes.route("/rule", methods=["PUT"])
@permissions.login_required
def create_rule():

    requestData = request.get_json()
    if requestData is None:
        raise BadRequest("Empty request data")

    code_notification_method = requestData.get("code_notification_method", "")
    code_notification_category = requestData.get("code_notification_category", "")

    # Save notification in database as UNREAD
    new_rule = TNotificationsRules(
        id_role=g.current_user.id_role,
        code_notification_method=code_notification_method,
        code_notification_category=code_notification_category,
    )

    DB.session.add(new_rule)
    DB.session.commit()

    return jsonify(1)


# Delete all rules for current user
@routes.route("/rules", methods=["DELETE"])
@permissions.login_required
def delete_all_rules():

    nbRulesDeleted = TNotificationsRules.query.filter(
        TNotificationsRules.id_role == g.current_user.id_role
    ).delete()
    DB.session.commit()
    return jsonify(nbRulesDeleted)


# add rule for user
@routes.route("/rule", methods=["DELETE"])
@permissions.login_required
def modify_rules():

    requestData = request.get_json()
    if requestData is None:
        raise BadRequest("Empty request data")

    code_notification_method = requestData.get("code_notification_method", "")
    code_notification_category = requestData.get("code_notification_category", "")

    nbRulesDeleted = TNotificationsRules.query.filter(
        TNotificationsRules.id_role == g.current_user.id_role,
        TNotificationsRules.code_notification_category == code_notification_category,
        TNotificationsRules.code_notification_method == code_notification_method,
    ).delete()
    DB.session.commit()
    return jsonify(nbRulesDeleted)


# Get all availabe method for notification
@routes.route("/methods", methods=["GET"])
@permissions.login_required
def list_notification_methods():
    notificationMethods = BibNotificationsMethods.query.all()
    result = [
        notificationsMethod.as_dict(
            fields=[
                "code_notification_method",
                "label_notification_method",
                "description_notification_method",
            ]
        )
        for notificationsMethod in notificationMethods
    ]
    return jsonify(result)


# Get all availabe category for notification
@routes.route("/categories", methods=["GET"])
@permissions.login_required
def list_notification_categories():
    notificationCategories = BibNotificationsCategories.query.all()
    result = [
        notificationsCategory.as_dict(
            fields=[
                "code_notification_category",
                "label_notification_category",
                "description_notification_category",
            ]
        )
        for notificationsCategory in notificationCategories
    ]
    return jsonify(result)
