DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.alembic_version) THEN
        RAISE EXCEPTION 'PartGraph baseline stamp requires an empty alembic_version table';
    END IF;

    INSERT INTO public.alembic_version (version_num)
    VALUES ('0046_pipeline_actor_roles');
END
$$;
