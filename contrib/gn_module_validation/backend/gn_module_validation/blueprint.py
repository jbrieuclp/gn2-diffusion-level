import logging
import datetime
import json
from geojson import FeatureCollection

from flask import Blueprint, request, jsonify
from flask.globals import session
from flask.json import jsonify
import sqlalchemy as sa
from sqlalchemy import select, func
from sqlalchemy.sql.expression import cast, outerjoin
from sqlalchemy.sql.sqltypes import Integer
from sqlalchemy.orm import aliased, joinedload, contains_eager
from marshmallow import ValidationError

from utils_flask_sqla.response import json_resp
from utils_flask_sqla.serializers import SERIALIZERS
from pypnnomenclature.models import TNomenclatures, BibNomenclaturesTypes

from geonature.utils.env import DB, db
from geonature.utils.utilssqlalchemy import test_is_uuid
from geonature.core.gn_synthese.models import Synthese
from geonature.core.gn_synthese.utils.query_select_sqla import SyntheseQuery
from geonature.core.gn_permissions import decorators as permissions
from geonature.core.gn_commons.schemas import TValidationSchema
from geonature.core.gn_commons.models.base import TValidations

from werkzeug.exceptions import BadRequest
from geonature.core.gn_commons.models import TValidations

from .models import VSyntheseValidation

blueprint = Blueprint("validation", __name__)
log = logging.getLogger()


@blueprint.route("", methods=["GET", "POST"])
@permissions.check_cruved_scope("R", True, module_code="VALIDATION")
def get_synthese_data(info_role):
    """
    Return synthese and t_validations data filtered by form params
    Params must have same synthese fields names

    .. :quickref: Validation;

    Parameters:
    ------------
    info_role (User):
        Information about the user asking the route. Auto add with kwargs

    Returns
    -------
    FeatureCollection
    """

    fields = {
        'id_synthese',
        'unique_id_sinp',
        'entity_source_pk_value',
        'meta_update_date',
        'id_nomenclature_valid_status',
        'nomenclature_valid_status.cd_nomenclature',
        'nomenclature_valid_status.mnemonique',
        'nomenclature_valid_status.label_default',
        'last_validation.validation_date',
        'last_validation.validation_auto',
        'taxref.cd_nom',
        'taxref.nom_vern',
        'taxref.lb_nom',
        'taxref.nom_vern_or_lb_nom',
        'profile.score',
        'profile.valid_phenology',
        'profile.valid_altitude',
        'profile.valid_distribution',
    }
    fields |= { col['column_name']
               for col in blueprint.config["COLUMN_LIST"] }

    filters = request.json

    result_limit = filters.pop("limit", blueprint.config["NB_MAX_OBS_MAP"])

    """
    1) We start creating the query with SQLAlchemy ORM.
    2) We convert this query to SQLAlchemy Core in order to use
       SyntheseQuery utility class to apply user filters.
    3) We get back the results in the ORM through from_statement.
       We populate relationships with contains_eager.

    We create a lot of aliases, that are selected at step 1, 
    and given to contains_eager at step 3 to correctly identify columns
    to use to populate relationships models.
    """
    last_validation_subquery = (
        TValidations.query
        .filter(TValidations.uuid_attached_row==Synthese.unique_id_sinp)
        .order_by(TValidations.validation_date.desc())
        .limit(1)
        .subquery()
        .lateral('last_validation')
    )
    last_validation = aliased(TValidations, last_validation_subquery)
    relationships = list({
        field.split('.', 1)[0]
        for field in fields
        if '.' in field and not field.startswith('last_validation.')
    })
    profile_index = relationships.index('profile')
    relationships = [ getattr(Synthese, rel) for rel in relationships ]
    aliases = [
        aliased(rel.property.mapper.class_)
        for rel in relationships
    ]
    profile_alias = aliases[profile_index]  # for later use in filters

    query = (
        db.session.query(
            Synthese,
            *aliases,
            last_validation,
        )
    )
    for rel, alias in zip(relationships, aliases):
        query = query.outerjoin(rel.of_type(alias))
    query = (
        query
        .outerjoin(last_validation, sa.true())
        .filter(Synthese.the_geom_4326.isnot(None))
        .order_by(Synthese.date_min.desc())
    )

    # filter with profile
    score = filters.pop("score", None)
    if score is not None:
        query = query.filter(profile_alias.score==score)
    valid_distribution = filters.pop("valid_distribution", None)
    if valid_distribution is not None:
        query = query.filter(profile_alias.valid_distribution.is_(valid_distribution))
    valid_altitude = filters.pop("valid_altitude", None)
    if valid_altitude is not None:
        query = query.filter(profile_alias.valid_altitude.is_(valid_altitude))
    valid_phenology = filters.pop("valid_phenology", None)
    if valid_phenology is not None:
        query = query.filter(profile_alias.valid_phenology.is_(valid_phenology))
    if filters.pop("modif_since_validation", None):
        query = query.filter(Synthese.meta_update_date > last_validation.validation_date)

    # Step 2: give SyntheseQuery the Core selectable from ORM query
    assert(len(query.selectable.froms) == 1)
    query = (
        SyntheseQuery(Synthese, query.selectable, filters,
                      query_joins=query.selectable.froms[0])
        .filter_query_all_filters(info_role)
        .limit(result_limit)
    )

    # Step 3: Construct Synthese model from query result
    query = (
        Synthese.query
        .options(*[contains_eager(rel, alias=alias) for rel, alias in zip(relationships, aliases)])
        .options(contains_eager(Synthese.last_validation, alias=last_validation))
        .from_statement(query)
    )

    # The raise option ensure that we have correctly retrived relationships data at step 3
    return jsonify(
        query.as_geofeaturecollection(fields=fields, unloaded='raise')
    )


@blueprint.route("/statusNames", methods=["GET"])
@permissions.check_cruved_scope("R", True, module_code="VALIDATION")
def get_statusNames(info_role):
    nomenclatures = (
        TNomenclatures.query
        .join(BibNomenclaturesTypes)
        .filter(BibNomenclaturesTypes.mnemonique == "STATUT_VALID")
        .filter(TNomenclatures.active == True)
        .order_by(TNomenclatures.cd_nomenclature)
    )
    return jsonify([
            nomenc.as_dict(fields=['id_nomenclature', 'mnemonique',
                                   'cd_nomenclature', 'definition_default'])
            for nomenc in nomenclatures.all()
    ])


@blueprint.route("/<id_synthese>", methods=["POST"])
@permissions.check_cruved_scope("C", True, module_code="VALIDATION")
def post_status(info_role, id_synthese):
    data = dict(request.get_json())
    try:
        id_validation_status = data["statut"]
    except KeyError:
        raise BadRequest("Aucun statut de validation n'est sélectionné")
    try:
        validation_comment = data["comment"]
    except KeyError:
        raise BadRequest("Missing 'comment'")

    id_synthese = id_synthese.split(",")

    for id in id_synthese:
        # t_validations.id_validation:

        # t_validations.uuid_attached_row:
        uuid = DB.session.query(Synthese.unique_id_sinp).filter(
            Synthese.id_synthese == int(id)
        ).one()

        # t_validations.id_validator:
        id_validator = info_role.id_role

        # t_validations.validation_date
        val_date = datetime.datetime.now()

        # t_validations.validation_auto
        val_auto = False
        val_dict = {
            "uuid_attached_row": uuid[0],
            "id_nomenclature_valid_status": id_validation_status,
            "id_validator" : id_validator,
            "validation_comment" : validation_comment,
            "validation_date": str(val_date),
            "validation_auto" : val_auto,
        }
        # insert values in t_validations
        validationSchema = TValidationSchema()
        try:
            validation = validationSchema.load(
                val_dict, instance=TValidations(),
                session=DB.session
                )
        except ValidationError as error:
            raise BadRequest(error.messages)
        DB.session.add(validation)
        DB.session.commit()

    return jsonify(data)


@blueprint.route("/date/<uuid:uuid>", methods=["GET"])
def get_validation_date(uuid):
    """
    Retourne la date de validation
    pour l'observation uuid
    """
    s = (
        Synthese.query
        .filter_by(unique_id_sinp=uuid)
        .lateraljoin_last_validation()
        .first_or_404()
    )
    if s.last_validation:
        return jsonify(str(s.last_validation.validation_date))
    else:
        return '', 204
