import pytest

from flask import url_for, current_app
from sqlalchemy import func
import sqlalchemy as sa
from werkzeug.exceptions import Forbidden
from jsonschema import validate as validate_json

from geonature.utils.env import db
from geonature.core.ref_geo.models import LAreas

from . import *
from .fixtures import *


@pytest.mark.usefixtures("client_class", "temporary_transaction")
class TestSynthese:
    def test_list_sources(self):
        response = self.client.get(url_for("gn_synthese.get_sources"))
        assert response.status_code == 200
        data = response.get_json()
        assert(len(data) > 0)

    def test_get_defaut_nomenclatures(self):
        response = self.client.get(url_for("gn_synthese.getDefaultsNomenclatures"))
        assert response.status_code == 200

    @pytest.mark.skip()
    def test_get_synthese_data(self):
        login(self.client)
        # test on synonymy and taxref attrs
        query_string = {
            "cd_ref": 209902,
            "taxhub_attribut_102": "eau",
            "taxonomy_group2_inpn": "Insectes",
            "taxonomy_id_hab": 3,
        }
        response = self.client.get(
            url_for("gn_synthese.get_observations_for_web"), query_string=query_string
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]["features"]) == 1
        # clés obligatoire pour le fonctionnement du front
        assert "cd_nom" in data["data"]["features"][0]["properties"]
        assert "id" in data["data"]["features"][0]["properties"]
        assert "url_source" in data["data"]["features"][0]["properties"]
        assert "entity_source_pk_value" in data["data"]["features"][0]["properties"]
        assert data["data"]["features"][0]["properties"]["cd_nom"] == 713776

        # test geometry filters
        key_municipality = "area_" + str(current_app.config["BDD"]["id_area_type_municipality"])
        query_string = {
            "geoIntersection": """
                POLYGON ((5.580368041992188 43.42100882994726, 5.580368041992188 45.30580259943578, 8.12919616699219 45.30580259943578, 8.12919616699219 43.42100882994726, 5.580368041992188 43.42100882994726))
                """,
            key_municipality: 28290,
        }
        response = self.client.get(url_for("gn_synthese.get_observations_for_web"), query_string=query_string)
        data = response.get_json()
        assert len(data["data"]) >= 2

        # test geometry filter with circle radius
        query_string = {
            "geoIntersection": "POINT (6.121788024902345 45.06794388950998)",
            "radius": "83883.94104436478",
        }

        response = self.client.get(url_for("gn_synthese.get_observations_for_web"), query_string=query_string)
        data = response.get_json()
        assert len(data["data"]) >= 2

        # test organisms and multiple same arg in query string

        response = self.client.get("/synthese/for_web?id_organism=1&id_organism=2")
        data = response.get_json()
        assert len(data["data"]) >= 2

    @pytest.mark.skip()
    def test_get_synthese_data_cruved(self):
        # test cruved
        login(self.client, username="partenaire", password="admin")

        response = self.client.get(url_for("gn_synthese.get_observations_for_web"))
        data = response.get_json()

        assert len(data["data"]["features"]) > 0
        assert response.status_code == 200

    @pytest.mark.skip()
    def test_filter_cor_observers(self):
        """
            Test avec un cruved R2 qui join sur cor_synthese_observers
        """
        login(self.client, username="test_cruved_r2", password="admin")
        response = self.client.get(url_for("gn_synthese.get_observations_for_web"))
        data = response.get_json()

        # le résultat doit être supérieur ou égal à 2
        assert len(data["data"]["features"]) != 0
        # le requete doit etre OK marlgré la geom NULL
        assert response.status_code == 200

    @pytest.mark.skip()
    def test_export(self):
        login(self.client)

        # csv
        response = self.client.post(
            url_for("gn_synthese.export_observations_web"),
            data=[1, 2, 3],
            query_string={"export_format": "csv"},
        )

        assert response.status_code == 200

        response = self.client.post(
            url_for("gn_synthese.export_observations_web"),
            data=[1, 2, 3],
            query_string={"export_format": "geojson"},
        )
        assert response.status_code == 200

        response = self.client.post(
            url_for("gn_synthese.export_observations_web"),
            data=[1, 2, 3],
            query_string={"export_format": "shapefile"},
        )
        assert response.status_code == 200

    def test_export_status(self):
        login(self.client)

        response = self.client.post(url_for("gn_synthese.export_status"))

        assert response.status_code == 200

    def test_export_metadata(self):
        login(self.client)

        response = self.client.get(url_for("gn_synthese.export_metadata"))

        assert response.status_code == 200

    def test_general_stat(self):
        login(self.client)

        response = self.client.get(url_for("gn_synthese.general_stats"))

        assert response.status_code == 200

    def test_get_one_synthese_record(self, app, users, synthese_data):
        from geonature.core.gn_synthese.models import Synthese

        response = self.client.get(
            url_for("gn_synthese.get_one_synthese", id_synthese=synthese_data[0].id_synthese))
        assert response.status_code == 401

        set_logged_user_cookie(self.client, users['noright_user'])
        response = self.client.get(
            url_for("gn_synthese.get_one_synthese", id_synthese=synthese_data[0].id_synthese))
        assert response.status_code == 403

        set_logged_user_cookie(self.client, users['admin_user'])
        not_existing = db.session.query(func.max(Synthese.id_synthese)).scalar() + 1
        response = self.client.get(
            url_for("gn_synthese.get_one_synthese", id_synthese=not_existing))
        assert response.status_code == 404

        set_logged_user_cookie(self.client, users['admin_user'])
        response = self.client.get(
            url_for("gn_synthese.get_one_synthese", id_synthese=synthese_data[0].id_synthese))
        assert response.status_code == 200

        set_logged_user_cookie(self.client, users['self_user'])
        response = self.client.get(
            url_for("gn_synthese.get_one_synthese", id_synthese=synthese_data[0].id_synthese))
        assert response.status_code == 200

        set_logged_user_cookie(self.client, users['user'])
        response = self.client.get(
            url_for("gn_synthese.get_one_synthese", id_synthese=synthese_data[0].id_synthese))
        assert response.status_code == 200

        set_logged_user_cookie(self.client, users['associate_user'])
        response = self.client.get(
            url_for("gn_synthese.get_one_synthese", id_synthese=synthese_data[0].id_synthese))
        assert response.status_code == 200

        set_logged_user_cookie(self.client, users['stranger_user'])
        response = self.client.get(
            url_for("gn_synthese.get_one_synthese", id_synthese=synthese_data[0].id_synthese))
        assert response.status_code == Forbidden.code

    def test_color_taxon(self):
        # Note: require grids 5×5!
        response = self.client.get(url_for("gn_synthese.get_color_taxon"))
        assert response.status_code == 200
        data = response.get_json()
        validate_json(instance=data, schema={
            'type': 'array',
            'minItems': 1,
            'items': {
                'type': 'object',
                'properties': {
                    'cd_nom': { 'type': 'integer', },
                    'id_area': { 'type': 'integer', },
                    'color': { 'type': 'string', },
                    'nb_obs': { 'type': 'integer', },
                    'last_date': { 'type': 'string', },
                },
                'minProperties': 5,
                'additionalProperties': False,
            },
        })
