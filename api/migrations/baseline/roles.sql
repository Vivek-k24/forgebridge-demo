DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'partgraph_collector') THEN
        CREATE ROLE partgraph_collector NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'partgraph_app') THEN
        CREATE ROLE partgraph_app NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'partgraph_reviewer') THEN
        CREATE ROLE partgraph_reviewer NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'partgraph_contributor') THEN
        CREATE ROLE partgraph_contributor NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'partgraph_curator') THEN
        CREATE ROLE partgraph_curator NOLOGIN;
    END IF;
END
$$;

GRANT partgraph_app TO CURRENT_USER WITH INHERIT FALSE, SET TRUE;
GRANT partgraph_reviewer TO CURRENT_USER WITH INHERIT FALSE, SET TRUE;
GRANT partgraph_contributor TO CURRENT_USER WITH INHERIT FALSE, SET TRUE;
GRANT partgraph_curator TO CURRENT_USER WITH INHERIT FALSE, SET TRUE;
