import json
import logging
from flask import Blueprint, current_app, request,render_template
import pprint

from sqlalchemy import or_
from sqlalchemy.sql import text

from geonature.utils.env import DB
from geonature.core.gn_synthese.models import Synthese

from pypnnomenclature.models import TNomenclatures
from pypnusershub.db.tools import InsufficientRightsError

import datetime as dt
from binascii import a2b_base64

from geonature.core.gn_meta.models import (
    TDatasets,
    TDatasetDetails,
    CorDatasetActor,
    TAcquisitionFramework,
    CorAcquisitionFrameworkActor,
    CorAcquisitionFrameworkObjectif,
    CorAcquisitionFrameworkVoletSINP,
)
from geonature.core.gn_commons.models import TModules
from geonature.core.gn_meta.repositories import get_datasets_cruved, get_af_cruved
from utils_flask_sqla.response import json_resp
from geonature.core.gn_permissions import decorators as permissions
from geonature.core.gn_meta import mtd_utils
from geonature.utils.errors import GeonatureApiError
import geonature.utils.filemanager as fm

from flask.wrappers import Response

routes = Blueprint("gn_meta", __name__)

# get the root logger
log = logging.getLogger()
gunicorn_error_logger = logging.getLogger("gunicorn.error")


@routes.route("/list/datasets", methods=["GET"])
@json_resp
def get_datasets_list():
    q = DB.session.query(TDatasets)
    data = q.all()
    return [d.as_dict(columns=("id_dataset", "dataset_name")) for d in data]


# TODO: quel cruved on recupère sur une route comme celle là
# celui du module admin (meta) ou celui de geonature (route utilisé dans tous les modules...)
@routes.route("/datasets", methods=["GET"])
@permissions.check_cruved_scope("R", True)
@json_resp
def get_datasets(info_role):
    """
    Get datasets list
    
    .. :quickref: Metadata;

    :param info_role: add with kwargs
    :type info_role: TRole
    :query boolean active: filter on active fiel
    :query int id_acquisition_framework: get only dataset of given AF
    :returns:  `dict{'data':list<TDatasets>, 'with_erros': <boolean>}`
    """
    with_mtd_error = False
    if current_app.config["CAS_PUBLIC"]["CAS_AUTHENTIFICATION"]:
        # synchronise the CA and JDD from the MTD WS
        try:
            mtd_utils.post_jdd_from_user(
                id_user=info_role.id_role, id_organism=info_role.id_organisme
            )
        except Exception as e:
            gunicorn_error_logger.info(e)
            log.error(e)
            with_mtd_error = True
    params = request.args.to_dict()
    datasets = get_datasets_cruved(info_role, params)
    datasets_resp = {"data": datasets}
    if with_mtd_error:
        datasets_resp["with_mtd_errors"] = True
    if not datasets:
        return datasets_resp, 404
    return datasets_resp


@routes.route("/dataset/<id_dataset>", methods=["GET"])
@json_resp
def get_dataset(id_dataset):
    """
    Get one dataset

    .. :quickref: Metadata;

    :param id_dataset: the id_dataset
    :param type: int
    :returns: dict<TDataset>
    """
    data = DB.session.query(TDatasets).get(id_dataset)
    cor = data.cor_dataset_actor
    dataset = data.as_dict(True)
    organisms = []
    for c in cor:
        if c.organism:
            organisms.append(c.organism.as_dict())
        else:
            organisms.append(None)
    i = 0
    for o in organisms:
        dataset["cor_dataset_actor"][i]["organism"] = o
        i = i + 1
    return dataset


def get_dataset_details_dict(id_dataset):
    data = DB.session.query(TDatasetDetails).get(id_dataset)
    cor = data.cor_dataset_actor
    dataset = data.as_dict(True)
    organisms = []
    for c in cor:
        if c.organism:
            organisms.append(c.organism.as_dict())
        else:
            organisms.append(None)
    i = 0
    for o in organisms:
        dataset["cor_dataset_actor"][i]["organism"] = o
        i = i + 1
    if dataset["keywords"]:
        dataset["keywords"] = dataset["keywords"].split(' ')
    dataset["data_type"] = data.data_type.as_dict()
    dataset["dataset_objectif"] = data.dataset_objectif.as_dict()
    dataset["collecting_method"] = data.collecting_method.as_dict()
    dataset["data_origin"] = data.data_origin.as_dict()
    dataset["source_status"] = data.source_status.as_dict()
    dataset["resource_type"] = data.resource_type.as_dict()
    dataset["acquisition_framework"] = data.acquisition_framework.as_dict()
    dataset["taxa_count"] = DB.session.query(Synthese.cd_nom).filter(Synthese.id_dataset == id_dataset).distinct().count()
    dataset["observation_count"] = DB.session.query(Synthese.cd_nom).filter(Synthese.id_dataset == id_dataset).count()
    return dataset

@routes.route("/dataset_details/<id_dataset>", methods=["GET"])
@permissions.check_cruved_scope("R", True, module_code="METADATA")
@json_resp
def get_dataset_details(info_role, id_dataset):
    """
    Get one dataset with nomenclatures and af

    .. :quickref: Metadata;

    :param id_dataset: the id_dataset
    :param type: int
    :returns: dict<TDatasetDetails>
    """

    return get_dataset_details_dict(id_dataset)


@routes.route("/upload_canvas", methods=["POST"])
@json_resp
def upload_canvas():
    """Upload the canvas as a temporary image used while generating the pdf file
    """
    data = request.data[22:]
    binary_data = a2b_base64(data)

    fd = open('static/images/taxa.png', 'wb')
    fd.write(binary_data)
    fd.close()

    return "OK"


@routes.route("/dataset", methods=["POST"])
@permissions.check_cruved_scope("C", True, module_code="METADATA")
@json_resp
def post_dataset(info_role):
    """
    Post a dataset

    .. :quickref: Metadata;
    """
    if info_role.value_filter == "0":
        raise InsufficientRightsError(
            ('User "{}" cannot "{}" a dataset').format(
                info_role.id_role, info_role.code_action
            ),
            403,
        )

    data = dict(request.get_json())
    cor_dataset_actor = data.pop("cor_dataset_actor")
    modules = data.pop("modules")

    dataset = TDatasets(**data)
    for cor in cor_dataset_actor:
        # remove id_cda if None otherwise merge no working well
        if "id_cda" in cor and cor["id_cda"] is None:
            cor.pop("id_cda")
        dataset.cor_dataset_actor.append(CorDatasetActor(**cor))

    # init the relationship as an empty list
    modules_obj = (
        DB.session.query(TModules).filter(TModules.id_module.in_(modules)).all()
    )
    dataset.modules = modules_obj
    if dataset.id_dataset:
        DB.session.merge(dataset)
    else:
        DB.session.add(dataset)
    DB.session.commit()
    return dataset.as_dict(True)

@routes.route("/dataset/export_pdf/<id_dataset>", methods=["GET"])
@permissions.check_cruved_scope("C", True, module_code="METADATA")
def get_export_pdf_dataset(id_dataset, info_role):
    """
    Get a PDF export of one dataset
    """
    
    #Verification des droits
    if info_role.value_filter == "0":
        raise InsufficientRightsError(
            ('User "{}" cannot "{}" a dataset').format(
                info_role.id_role, 'export'
            ),
            403,
        )

    df = get_dataset_details_dict(id_dataset)
    if not df:
        return render_template(
            'error.html',
            error='Le dataset presente des erreurs',
            redirect=current_app.config["URL_APPLICATION"]+'/#/metadata'), 404

    if len(df["dataset_desc"]) > 240:
        df["dataset_desc"] = df["dataset_desc"][:240] + '...'

    filename = 'jeu_de_donnees_id_n_{}.pdf'.format(id_dataset)

    df['css'] = {
        "logo" : "Logo_SINP.png",
        "bandeau" : "Bandeau_SINP.png",
        "entite" : "sinp"
    }

    date = dt.datetime.now().strftime("%d/%m/%Y")

    df['footer'] = {
        "url" : current_app.config["URL_APPLICATION"]+"/api/meta/dataset/export_pdf/"+id_dataset,
        "date" : date
    }

    # Appel de la methode pour generer un pdf
    pdf_file = fm.generate_pdf('jeu_de_donnees_template_pdf.html', df, filename)

    return Response(
        pdf_file,
        mimetype="application/pdf",
        headers={
            "Content-disposition": "attachment; filename=" + filename,
            "Content-type": "application/pdf"
        }
    )

@routes.route("/acquisition_frameworks", methods=["GET"])
@permissions.check_cruved_scope("R", True)
@json_resp
def get_acquisition_frameworks(info_role):
    """
    Get all AF with cruved filter

    .. :quickref: Metadata;

    """
    params = request.args
    return get_af_cruved(info_role, params)


@routes.route("/acquisition_framework/<id_acquisition_framework>", methods=["GET"])
@json_resp
def get_acquisition_framework(id_acquisition_framework):
    """
    Get one AF

    .. :quickref: Metadata;

    :param id_acquisition_framework: the id_acquisition_framework
    :param type: int
    """
    af = DB.session.query(TAcquisitionFramework).get(id_acquisition_framework)
    if af:
        return af.as_dict(True)
    return None


@routes.route("/acquisition_framework", methods=["POST"])
@permissions.check_cruved_scope("C", True, module_code="METADATA")
@json_resp
def post_acquisition_framework(info_role):
    """
    Post a dataset
    .. :quickref: Metadata;
    """
    if info_role.value_filter == "0":
        raise InsufficientRightsError(
            ('User "{}" cannot "{}" a dataset').format(
                info_role.id_role, info_role.code_action
            ),
            403,
        )
    data = dict(request.get_json())

    cor_af_actor = data.pop("cor_af_actor")
    cor_objectifs = data.pop("cor_objectifs")
    cor_volets_sinp = data.pop("cor_volets_sinp")

    af = TAcquisitionFramework(**data)

    for cor in cor_af_actor:
        # remove id_cda if None otherwise merge no working well
        if "id_cafa" in cor and cor["id_cafa"] is None:
            cor.pop("id_cafa")
        af.cor_af_actor.append(CorAcquisitionFrameworkActor(**cor))

    if cor_objectifs is not None:
        objectif_nom = (
            DB.session.query(TNomenclatures)
            .filter(TNomenclatures.id_nomenclature.in_(cor_objectifs))
            .all()
        )
        for obj in objectif_nom:
            af.cor_objectifs.append(obj)

    if cor_volets_sinp is not None:
        volet_nom = (
            DB.session.query(TNomenclatures)
            .filter(TNomenclatures.id_nomenclature.in_(cor_volets_sinp))
            .all()
        )
        for volet in volet_nom:
            af.cor_volets_sinp.append(volet)
    if af.id_acquisition_framework:
        DB.session.merge(af)
    else:
        DB.session.add(af)
    DB.session.commit()
    return af.as_dict()


def get_cd_nomenclature(id_type, cd_nomenclature):
    query = "SELECT ref_nomenclatures.get_id_nomenclature(:id_type, :cd_n)"
    result = DB.engine.execute(
        text(query), id_type=id_type, cd_n=cd_nomenclature
    ).first()
    value = None
    if len(result) >= 1:
        value = result[0]
    return value


@routes.route("/aquisition_framework_mtd/<uuid_af>", methods=["POST"])
@json_resp
def post_acquisition_framework_mtd(uuid=None, id_user=None, id_organism=None):
    """ 
    Post an acquisition framwork from MTD web service in XML
    .. :quickref: Metadata;
    """
    return mtd_utils.post_acquisition_framework(
        uuid=uuid, id_user=id_user, id_organism=id_organism
    )


@routes.route("/dataset_mtd/<id_user>", methods=["POST"])
@routes.route("/dataset_mtd/<id_user>/<id_organism>", methods=["POST"])
@json_resp
def post_jdd_from_user_id(id_user=None, id_organism=None):
    """ 
    Post a jdd from the mtd XML
    .. :quickref: Metadata;
    """
    return mtd_utils.post_jdd_from_user(id_user=id_user, id_organism=id_organism)

