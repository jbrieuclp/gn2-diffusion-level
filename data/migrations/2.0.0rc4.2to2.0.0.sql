-- Migration du metadata comme un module à part

INSERT INTO gn_commons.t_modules(module_code, module_label, module_picto, module_desc, module_path, module_target, active_frontend, active_backend) VALUES
('METADATA', 'Metadonnées', 'fa-book', 'Module de gestion des métadonnées', 'metadata', '_self', TRUE, TRUE)
;

-- migration des permission dans le nouveau module
INSERT INTO gn_permissions.cor_role_action_filter_module_object(
  id_role,
  id_action,
  id_filter,
  id_module
)
WITH mod_admin AS (
    SELECT id_module
    FROM gn_commons.t_modules
    WHERE module_code ILIKE 'ADMIN'
),
obj AS (
    SELECT id_object
    FROM gn_permissions.t_objects
    WHERE code_object ILIKE 'METADATA'
),
mod_metadata AS (
    SELECT id_module
    FROM gn_commons.t_modules
    WHERE module_code ILIKE 'METADATA' 
)
SELECT id_role, id_action, id_filter, mod_metadata.id_module
FROM gn_permissions.cor_role_action_filter_module_object cor, mod_admin, obj, mod_metadata
WHERE cor.id_module = mod_admin.id_module AND cor.id_object = obj.id_object;

-- suppression des permissions de l'objet metadata inutiles
DELETE 
FROM gn_permissions.cor_role_action_filter_module_object
WHERE id_object = (
    SELECT id_object FROM gn_permissions.t_objects WHERE code_object = 'METADATA'
) AND id_module = (
    SELECT id_module FROM gn_commons.t_modules WHERE module_code = 'ADMIN'
);


-- suppression relation cor_object_module 
DELETE FROM gn_permissions.cor_object_module WHERE id_object = (
    SELECT id_object FROM gn_permissions.t_objects WHERE code_object = 'METADATA'
);

-- supression de l'objet metadata
DELETE FROM gn_permissions.t_objects where code_object = 'METADATA'

-- Droit limité pour le groupe en poste pour le module METADATA
INSERT INTO gn_permissions.cor_role_action_filter_module_object(id_role, id_action,id_filter,id_module)
SELECT 7, 1, 1, id_module
FROM gn_commons.t_modules
WHERE module_code = 'METADATA';

INSERT INTO gn_permissions.cor_role_action_filter_module_object(id_role, id_action,id_filter,id_module)
SELECT 7, 2, 3, id_module
FROM gn_commons.t_modules
WHERE module_code = 'METADATA';

INSERT INTO gn_permissions.cor_role_action_filter_module_object(id_role, id_action,id_filter,id_module)
SELECT 7, 3, 1, id_module
FROM gn_commons.t_modules
WHERE module_code = 'METADATA';

INSERT INTO gn_permissions.cor_role_action_filter_module_object(id_role, id_action,id_filter,id_module)
SELECT 7, 4, 1, id_module
FROM gn_commons.t_modules
WHERE module_code = 'METADATA';

INSERT INTO gn_permissions.cor_role_action_filter_module_object(id_role, id_action,id_filter,id_module)
SELECT 7, 5, 3, id_module
FROM gn_commons.t_modules
WHERE module_code = 'METADATA';

INSERT INTO gn_permissions.cor_role_action_filter_module_object(id_role, id_action,id_filter,id_module)
SELECT 7, 6, 1, id_module
FROM gn_commons.t_modules
WHERE module_code = 'METADATA';


-- Update taxons_synthese_autocomplete

SELECT concat(aut.search_name,  ' - [', t.id_rang, ' - ', t.cd_nom , ']' )
FROM gn_synthese.taxons_synthese_autocomplete aut
JOIN taxonomie.taxref t ON aut.cd_nom = t.cd_nom;

CREATE OR REPLACE FUNCTION gn_synthese.fct_trg_refresh_taxons_forautocomplete()
  RETURNS trigger AS
$BODY$
 DECLARE
  BEGIN

    IF TG_OP in ('DELETE', 'TRUNCATE', 'UPDATE') AND OLD.cd_nom NOT IN (SELECT DISTINCT cd_nom FROM gn_synthese.synthese) THEN
        DELETE FROM gn_synthese.taxons_synthese_autocomplete auto
        WHERE auto.cd_nom = OLD.cd_nom;
    END IF;

    IF TG_OP in ('INSERT', 'UPDATE') AND NEW.cd_nom NOT IN (SELECT DISTINCT cd_nom FROM gn_synthese.taxons_synthese_autocomplete) THEN
      INSERT INTO gn_synthese.taxons_synthese_autocomplete
      SELECT t.cd_nom,
              t.cd_ref,
          concat(t.lb_nom, ' = <i>', t.nom_valide, '</i>', ' - [', t.id_rang, ' - ', t.cd_nom , ']') AS search_name,
          t.nom_valide,
          t.lb_nom,
          t.regne,
          t.group2_inpn
      FROM taxonomie.taxref t  WHERE cd_nom = NEW.cd_nom;
      INSERT INTO gn_synthese.taxons_synthese_autocomplete
      SELECT t.cd_nom,
        t.cd_ref,
        concat(t.nom_vern, ' =  <i> ', t.nom_valide, '</i>', ' - [', t.id_rang, ' - ', t.cd_nom , ']' ) AS search_name,
        t.nom_valide,
        t.lb_nom,
        t.regne,
        t.group2_inpn
      FROM taxonomie.taxref t  WHERE t.nom_vern IS NOT NULL AND cd_nom = NEW.cd_nom;
    END IF;
  RETURN NULL;
  END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;


CREATE OR REPLACE FUNCTION taxonomie.trg_fct_refresh_nomfrancais_mv_taxref_list_forautocomplete()
  RETURNS trigger AS
$BODY$
DECLARE
BEGIN
    UPDATE taxonomie.vm_taxref_list_forautocomplete v
    SET search_name = concat(NEW.nom_francais, ' =  <i> ', t.nom_valide, '</i>', ' - [', t.id_rang, ' - ', t.cd_nom , ']')
    FROM taxonomie.taxref t
		WHERE v.cd_nom = NEW.cd_nom AND t.cd_nom = NEW.cd_nom;
    RETURN NEW;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;



-- DELETE cascade sur ref_geo
ALTER TABLE ref_geo.li_municipalities DROP CONSTRAINT fk_li_municipalities_id_area;

ALTER TABLE ref_geo.li_municipalities
  ADD CONSTRAINT fk_li_municipalities_id_area FOREIGN KEY (id_area)
      REFERENCES ref_geo.l_areas (id_area) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE ref_geo.li_grids DROP CONSTRAINT fk_li_grids_id_area;

ALTER TABLE ref_geo.li_grids
  ADD CONSTRAINT fk_li_grids_id_area FOREIGN KEY (id_area)
      REFERENCES ref_geo.l_areas (id_area) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE CASCADE;


-- Contrainte unique sur UUID en synthese et occtax

ALTER TABLE ONLY gn_synthese.synthese
    ADD CONSTRAINT unique_id_sinp_unique UNIQUE (unique_id_sinp);

ALTER TABLE ONLY pr_occtax.cor_counting_occtax
    ADD CONSTRAINT unique_id_sinp_occtax_unique UNIQUE (unique_id_sinp_occtax);