-- DROP SCHEMA IF EXISTS ref_geo CASCADE;

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;


CREATE SCHEMA IF NOT EXISTS ref_geo;

SET search_path = ref_geo, pg_catalog;

----------------------
--TABLES & SEQUENCES--
----------------------
CREATE TABLE bib_areas_types (
    id_type integer NOT NULL,
    type_name character varying(200),
    type_desc text,
    ref_name character varying(200), 
    ref_version integer
);
COMMENT ON COLUMN bib_areas_types.ref_name IS 'Indique le nom du référentiel géographique utilisé pour ce type';
COMMENT ON COLUMN bib_areas_types.ref_version IS 'Indique l''année du référentiel utilisé';

CREATE SEQUENCE l_areas_id_area_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE l_areas (
    id_area integer NOT NULL,
    id_type integer NOT NULL,
    area_name character varying(250),
    geom public.geometry(MultiPolygon,MYLOCALSRID),
    centroid public.geometry(Point,MYLOCALSRID),
    source character varying(250),
    source_code character varying(25),
    comment text,
    meta_create_date timestamp without time zone,
    meta_update_date timestamp without time zone,
    CONSTRAINT enforce_geotype_l_areas_geom CHECK (((public.geometrytype(geom) = 'MULTIPOLYGON'::text) OR (geom IS NULL))),
    CONSTRAINT enforce_srid_l_areas_geom CHECK ((public.st_srid(geom) = MYLOCALSRID)),
    CONSTRAINT enforce_geotype_l_areas_centroid CHECK (((public.geometrytype(centroid) = 'POINT'::text) OR (centroid IS NULL))),
    CONSTRAINT enforce_srid_l_areas_centroid CHECK ((public.st_srid(centroid) = MYLOCALSRID))
);
ALTER SEQUENCE l_areas_id_area_seq OWNED BY l_areas.id_area;
ALTER TABLE ONLY l_areas ALTER COLUMN id_area SET DEFAULT nextval('l_areas_id_area_seq'::regclass);

CREATE TABLE l_municipalities (
    id_municipality character varying(25) NOT NULL,
    id_area integer NOT NULL,
    status character varying(22),
    fr_insee_com character varying(5),
    fr_nom_com character varying(50),
    fr_insee_arr character varying(2),
    fr_nom_dep character varying(30),
    fr_insee_dep character varying(3),
    fr_nom_reg character varying(35),
    fr_insee_reg character varying(2),
    fr_code_epci character varying(9),
    plani_precision double precision,
    siren_code character varying(10),
    canton character varying(200),
    population integer,
    multican character varying(3),
    cc_nom character varying(250),
    cc_siren bigint,
    cc_nature character varying(5),
    cc_date_creation character varying(10),
    cc_date_effet character varying(10),
    coeur boolean,
    aa boolean,
    pec boolean,
    apa boolean,
    massif character varying(50),
    insee_commune_nouvelle character varying(5),
    meta_create_date timestamp without time zone,
    meta_update_date timestamp without time zone
);

CREATE TABLE l_grids (
    id_grid character varying(50) NOT NULL,
    geom public.geometry(Polygon,MYLOCALSRID),
    centroid public.geometry(Point,MYLOCALSRID),
    cxmin integer,
    cxmax integer,
    cymin integer,
    cymax integer,
    code_grid_10k character varying(20),
    coeur boolean
);

CREATE TABLE dem_vector
(
  gid serial NOT NULL,
  geom public.geometry(Geometry,MYLOCALSRID),
  val double precision
);



----------------
--PRIMARY KEYS--
----------------
ALTER TABLE ONLY l_municipalities
    ADD CONSTRAINT pk_l_municipalities PRIMARY KEY (id_municipality);

ALTER TABLE ONLY l_grids
    ADD CONSTRAINT pk_l_grids PRIMARY KEY (id_grid);

ALTER TABLE ONLY l_areas
    ADD CONSTRAINT pk_l_areas PRIMARY KEY (id_area);

ALTER TABLE ONLY bib_areas_types
    ADD CONSTRAINT pk_bib_areas_types PRIMARY KEY (id_type);

ALTER TABLE ONLY dem_vector
    ADD CONSTRAINT pk_dem_vector PRIMARY KEY (gid);


----------------
--FOREIGN KEYS--
----------------
ALTER TABLE ONLY l_areas
    ADD CONSTRAINT fk_l_areas_id_type FOREIGN KEY (id_type) REFERENCES bib_areas_types(id_type) ON UPDATE CASCADE;

ALTER TABLE ONLY l_municipalities
    ADD CONSTRAINT fk_l_municipalities_id_area FOREIGN KEY (id_area) REFERENCES l_areas(id_area) ON UPDATE CASCADE;


---------
--INDEX--
---------
CREATE INDEX index_l_areas_geom ON l_areas USING gist (geom);
CREATE INDEX index_l_areas_centroid ON l_areas USING gist (centroid);
CREATE INDEX index_l_grids_geom ON l_grids USING gist (geom);
CREATE INDEX index_l_grids_centroid ON l_grids USING gist (centroid);
CREATE INDEX index_dem_vector_geom ON dem_vector USING gist (geom);

------------
--TRIGGERS--
------------
CREATE TRIGGER tri_meta_dates_change_l_areas BEFORE INSERT OR UPDATE ON l_areas FOR EACH ROW EXECUTE PROCEDURE public.fct_trg_meta_dates_change();
CREATE TRIGGER tri_meta_dates_change_l_municipalities BEFORE INSERT OR UPDATE ON l_municipalities FOR EACH ROW EXECUTE PROCEDURE public.fct_trg_meta_dates_change();


-------------
--FUNCTIONS--
-------------
CREATE OR REPLACE FUNCTION fct_get_altitude_intersection(IN mygeom public.geometry)
  RETURNS TABLE(altitude_min integer, altitude_max integer) AS
$BODY$
DECLARE
    isrid int;
BEGIN
    SELECT gn_meta.get_default_parameter('local_srid', NULL) INTO isrid;
    RETURN QUERY
    WITH d  as (
        SELECT st_transform(myGeom,isrid) a
     )
    SELECT min(val)::int as altitude_min, max(val)::int as altitude_max
    FROM ref_geo.dem_vector, d
    WHERE st_intersects(a,geom);

END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;


CREATE OR REPLACE FUNCTION fct_get_municipality_intersection(IN mygeom public.geometry)
  RETURNS TABLE(insee_code character varying, municipality_name character varying) AS
$BODY$
DECLARE
    isrid int;
BEGIN
    SELECT gn_meta.get_default_parameter('local_srid', NULL) INTO isrid;
    RETURN QUERY
    WITH d  as (
        SELECT st_transform(myGeom,isrid) geom_trans
    )
    SELECT a.source_code AS id_municipality, a.area_name 
    FROM ref_geo.l_areas a, d 
    WHERE a.id_type = 1 
    AND st_intersects(geom_trans, a.geom);

END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;


--------
--DATA--
--------

INSERT INTO bib_areas_types (id_type, type_name, type_desc, ref_name, ref_version) VALUES
(1,'communes', 'type communes', 'IGN admin_express', 2017)
,(2,'département', 'type département', 'IGN admin_express', 2017)
,(3,'maille 10*10', 'type maille inpn 10*10', NULL, NULL)
,(4,'espace naturel', 'type espace naturel', NULL, NULL)
,(5,'masse d''eau', 'type masse d''eau', NULL, NULL)
;