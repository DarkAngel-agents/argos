--
-- PostgreSQL database dump
--

\restrict boqcEib96QABcrQRdIGiPv7k2BhpmeSjwO1KWcCJ7jfwAqhVlPoEh4zJrGUVRGs

-- Dumped from database version 17.9 (Debian 17.9-1.pgdg13+1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: cristin; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA cristin;


ALTER SCHEMA cristin OWNER TO claude;

--
-- Name: lab; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA lab;


ALTER SCHEMA lab OWNER TO claude;

--
-- Name: set_updated_at(); Type: FUNCTION; Schema: lab; Owner: claude
--

CREATE FUNCTION lab.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$;


ALTER FUNCTION lab.set_updated_at() OWNER TO claude;

--
-- Name: agent_verif_rules_touch(); Type: FUNCTION; Schema: public; Owner: claude
--

CREATE FUNCTION public.agent_verif_rules_touch() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.agent_verif_rules_touch() OWNER TO claude;

--
-- Name: chat_scratchpad_touch(); Type: FUNCTION; Schema: public; Owner: claude
--

CREATE FUNCTION public.chat_scratchpad_touch() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.last_seen_at := NOW();
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.chat_scratchpad_touch() OWNER TO claude;

--
-- Name: cleanup_heartbeat(); Type: FUNCTION; Schema: public; Owner: claude
--

CREATE FUNCTION public.cleanup_heartbeat() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    DELETE FROM heartbeat_log WHERE id IN (
        SELECT id FROM heartbeat_log
        WHERE node = NEW.node AND service = NEW.service
        ORDER BY ts DESC OFFSET 30
    );
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.cleanup_heartbeat() OWNER TO claude;

--
-- Name: touch_updated_at(); Type: FUNCTION; Schema: public; Owner: claude
--

CREATE FUNCTION public.touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$;


ALTER FUNCTION public.touch_updated_at() OWNER TO claude;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: credentials; Type: TABLE; Schema: cristin; Owner: claude
--

CREATE TABLE cristin.credentials (
    id integer NOT NULL,
    resource_name character varying(100) NOT NULL,
    resource_ip character varying(15),
    credential_type character varying(30),
    username character varying(100),
    value_hint character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE cristin.credentials OWNER TO claude;

--
-- Name: credentials_id_seq; Type: SEQUENCE; Schema: cristin; Owner: claude
--

CREATE SEQUENCE cristin.credentials_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE cristin.credentials_id_seq OWNER TO claude;

--
-- Name: credentials_id_seq; Type: SEQUENCE OWNED BY; Schema: cristin; Owner: claude
--

ALTER SEQUENCE cristin.credentials_id_seq OWNED BY cristin.credentials.id;


--
-- Name: device_history; Type: TABLE; Schema: cristin; Owner: claude
--

CREATE TABLE cristin.device_history (
    id bigint NOT NULL,
    mac character varying(17) NOT NULL,
    ip character varying(15),
    status character varying(10) DEFAULT 'online'::character varying,
    uptime_seconds integer,
    tx_bytes bigint DEFAULT 0,
    rx_bytes bigint DEFAULT 0,
    signal integer,
    satisfaction integer,
    latency_ms double precision,
    recorded_at timestamp without time zone DEFAULT now()
);


ALTER TABLE cristin.device_history OWNER TO claude;

--
-- Name: device_history_id_seq; Type: SEQUENCE; Schema: cristin; Owner: claude
--

CREATE SEQUENCE cristin.device_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE cristin.device_history_id_seq OWNER TO claude;

--
-- Name: device_history_id_seq; Type: SEQUENCE OWNED BY; Schema: cristin; Owner: claude
--

ALTER SEQUENCE cristin.device_history_id_seq OWNED BY cristin.device_history.id;


--
-- Name: devices; Type: TABLE; Schema: cristin; Owner: claude
--

CREATE TABLE cristin.devices (
    id integer NOT NULL,
    mac character varying(17) NOT NULL,
    ip character varying(15),
    name character varying(100),
    hostname character varying(100),
    vendor character varying(100),
    device_type character varying(50),
    location character varying(100),
    is_static boolean DEFAULT false,
    fixed_ip character varying(15),
    switch_mac character varying(17),
    switch_port integer,
    vlan integer DEFAULT 1,
    first_seen timestamp without time zone DEFAULT now(),
    last_seen timestamp without time zone,
    notes text,
    active boolean DEFAULT true
);


ALTER TABLE cristin.devices OWNER TO claude;

--
-- Name: devices_id_seq; Type: SEQUENCE; Schema: cristin; Owner: claude
--

CREATE SEQUENCE cristin.devices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE cristin.devices_id_seq OWNER TO claude;

--
-- Name: devices_id_seq; Type: SEQUENCE OWNED BY; Schema: cristin; Owner: claude
--

ALTER SEQUENCE cristin.devices_id_seq OWNED BY cristin.devices.id;


--
-- Name: events; Type: TABLE; Schema: cristin; Owner: claude
--

CREATE TABLE cristin.events (
    id bigint NOT NULL,
    mac character varying(17),
    device_name character varying(100),
    ip character varying(15),
    category character varying(30) NOT NULL,
    severity character varying(10) DEFAULT 'info'::character varying,
    message text NOT NULL,
    raw_data jsonb,
    source character varying(20) DEFAULT 'unifi'::character varying,
    recorded_at timestamp without time zone DEFAULT now()
);


ALTER TABLE cristin.events OWNER TO claude;

--
-- Name: events_id_seq; Type: SEQUENCE; Schema: cristin; Owner: claude
--

CREATE SEQUENCE cristin.events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE cristin.events_id_seq OWNER TO claude;

--
-- Name: events_id_seq; Type: SEQUENCE OWNED BY; Schema: cristin; Owner: claude
--

ALTER SEQUENCE cristin.events_id_seq OWNED BY cristin.events.id;


--
-- Name: network_snapshots; Type: TABLE; Schema: cristin; Owner: claude
--

CREATE TABLE cristin.network_snapshots (
    id integer NOT NULL,
    snapshot_type character varying(30),
    data jsonb NOT NULL,
    recorded_at timestamp without time zone DEFAULT now()
);


ALTER TABLE cristin.network_snapshots OWNER TO claude;

--
-- Name: network_snapshots_id_seq; Type: SEQUENCE; Schema: cristin; Owner: claude
--

CREATE SEQUENCE cristin.network_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE cristin.network_snapshots_id_seq OWNER TO claude;

--
-- Name: network_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: cristin; Owner: claude
--

ALTER SEQUENCE cristin.network_snapshots_id_seq OWNED BY cristin.network_snapshots.id;


--
-- Name: decisions; Type: TABLE; Schema: lab; Owner: claude
--

CREATE TABLE lab.decisions (
    id integer NOT NULL,
    idea_id integer,
    title text NOT NULL,
    context text NOT NULL,
    decision text NOT NULL,
    rationale text,
    alternatives text,
    status text DEFAULT 'active'::text,
    decided_at timestamp with time zone DEFAULT now()
);


ALTER TABLE lab.decisions OWNER TO claude;

--
-- Name: decisions_id_seq; Type: SEQUENCE; Schema: lab; Owner: claude
--

CREATE SEQUENCE lab.decisions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE lab.decisions_id_seq OWNER TO claude;

--
-- Name: decisions_id_seq; Type: SEQUENCE OWNED BY; Schema: lab; Owner: claude
--

ALTER SEQUENCE lab.decisions_id_seq OWNED BY lab.decisions.id;


--
-- Name: discussions; Type: TABLE; Schema: lab; Owner: claude
--

CREATE TABLE lab.discussions (
    id integer NOT NULL,
    idea_id integer,
    author text DEFAULT 'argos'::text NOT NULL,
    message text NOT NULL,
    reply_to integer,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE lab.discussions OWNER TO claude;

--
-- Name: discussions_id_seq; Type: SEQUENCE; Schema: lab; Owner: claude
--

CREATE SEQUENCE lab.discussions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE lab.discussions_id_seq OWNER TO claude;

--
-- Name: discussions_id_seq; Type: SEQUENCE OWNED BY; Schema: lab; Owner: claude
--

ALTER SEQUENCE lab.discussions_id_seq OWNED BY lab.discussions.id;


--
-- Name: ideas; Type: TABLE; Schema: lab; Owner: claude
--

CREATE TABLE lab.ideas (
    id integer NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    category text DEFAULT 'general'::text NOT NULL,
    source text DEFAULT 'argos'::text,
    status text DEFAULT 'raw'::text NOT NULL,
    priority integer DEFAULT 5,
    tags text[] DEFAULT '{}'::text[],
    refs text[] DEFAULT '{}'::text[],
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE lab.ideas OWNER TO claude;

--
-- Name: ideas_id_seq; Type: SEQUENCE; Schema: lab; Owner: claude
--

CREATE SEQUENCE lab.ideas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE lab.ideas_id_seq OWNER TO claude;

--
-- Name: ideas_id_seq; Type: SEQUENCE OWNED BY; Schema: lab; Owner: claude
--

ALTER SEQUENCE lab.ideas_id_seq OWNED BY lab.ideas.id;


--
-- Name: implementations; Type: TABLE; Schema: lab; Owner: claude
--

CREATE TABLE lab.implementations (
    id integer NOT NULL,
    idea_id integer,
    title text NOT NULL,
    type text DEFAULT 'plan'::text NOT NULL,
    content text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    machine text,
    executed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE lab.implementations OWNER TO claude;

--
-- Name: implementations_id_seq; Type: SEQUENCE; Schema: lab; Owner: claude
--

CREATE SEQUENCE lab.implementations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE lab.implementations_id_seq OWNER TO claude;

--
-- Name: implementations_id_seq; Type: SEQUENCE OWNED BY; Schema: lab; Owner: claude
--

ALTER SEQUENCE lab.implementations_id_seq OWNED BY lab.implementations.id;


--
-- Name: agent_sessions; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.agent_sessions (
    id bigint NOT NULL,
    title text NOT NULL,
    goal text NOT NULL,
    phase character varying(20) DEFAULT 'starting'::character varying NOT NULL,
    iteration integer DEFAULT 0 NOT NULL,
    max_iterations integer DEFAULT 50 NOT NULL,
    active boolean DEFAULT true NOT NULL,
    parent_session_id bigint,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    last_active_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    current_task text,
    evidence jsonb DEFAULT '{"errors": [], "commands": [], "decisions": [], "llm_calls": [], "verifications": []}'::jsonb NOT NULL,
    autonomy_level integer DEFAULT 0 NOT NULL,
    llm_provider character varying(20),
    total_tokens integer DEFAULT 0 NOT NULL,
    total_cost_eur numeric(10,4) DEFAULT 0 NOT NULL,
    created_by character varying(50),
    CONSTRAINT agent_sessions_autonomy_level_check CHECK ((autonomy_level >= 0)),
    CONSTRAINT agent_sessions_phase_check CHECK (((phase)::text = ANY ((ARRAY['starting'::character varying, 'planning'::character varying, 'executing'::character varying, 'verifying'::character varying, 'fixing'::character varying, 'complete'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.agent_sessions OWNER TO claude;

--
-- Name: TABLE agent_sessions; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON TABLE public.agent_sessions IS 'ARGOS-Commander agent loop sessions - phase state + checkpoint + evidence chain. See Vikunja #214.';


--
-- Name: COLUMN agent_sessions.phase; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_sessions.phase IS 'starting->planning->executing->verifying->fixing(loop)->complete/failed/cancelled';


--
-- Name: COLUMN agent_sessions.iteration; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_sessions.iteration IS 'Current iteration count in exec/verify/fix loop, capped by max_iterations';


--
-- Name: COLUMN agent_sessions.parent_session_id; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_sessions.parent_session_id IS 'Reserved for sub-task decomposition (post-MVP, NULL in MVP). ON DELETE SET NULL keeps orphans queryable.';


--
-- Name: COLUMN agent_sessions.current_task; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_sessions.current_task IS 'Human-readable description of the step currently executing (updated each iteration)';


--
-- Name: COLUMN agent_sessions.evidence; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_sessions.evidence IS 'Semi-fixed JSONB: top-level keys commands/verifications/errors/decisions/llm_calls (documented in skill #92), values free-form';


--
-- Name: COLUMN agent_sessions.autonomy_level; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_sessions.autonomy_level IS 'Session ceiling using autonomy_rules.level scale (INT, >=0). Per-command autonomy check still runs via existing autonomy_rules. See Vikunja #215 for unification with autonomy_config.risk_level discrepancy.';


--
-- Name: COLUMN agent_sessions.created_by; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_sessions.created_by IS 'Origin of session: cli, api, sub_session, scheduler, user:name';


--
-- Name: agent_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

ALTER TABLE public.agent_sessions ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.agent_sessions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: agent_verification_rules; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.agent_verification_rules (
    id bigint NOT NULL,
    pattern text NOT NULL,
    rule_type character varying(20) NOT NULL,
    expected text,
    on_fail character varying(20) DEFAULT 'retry'::character varying NOT NULL,
    priority integer DEFAULT 100 NOT NULL,
    active boolean DEFAULT true NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT agent_verification_rules_on_fail_check CHECK (((on_fail)::text = ANY ((ARRAY['retry'::character varying, 'fix'::character varying, 'escalate'::character varying, 'abort'::character varying])::text[]))),
    CONSTRAINT agent_verification_rules_rule_type_check CHECK (((rule_type)::text = ANY ((ARRAY['exit_code'::character varying, 'grep'::character varying, 'grep_not'::character varying, 'file_exists'::character varying, 'http_200'::character varying, 'custom'::character varying])::text[])))
);


ALTER TABLE public.agent_verification_rules OWNER TO claude;

--
-- Name: TABLE agent_verification_rules; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON TABLE public.agent_verification_rules IS 'Verification chain rules for ARGOS-Commander - regex match on executed command string, define success criterion';


--
-- Name: COLUMN agent_verification_rules.pattern; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_verification_rules.pattern IS 'POSIX ERE regex matched against the executed command string (via ~ operator)';


--
-- Name: COLUMN agent_verification_rules.rule_type; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_verification_rules.rule_type IS 'exit_code=check $?, grep=stdout must contain expected, grep_not=stdout must NOT contain, file_exists=expected is path, http_200=curl check, custom=handler in agent loop code';


--
-- Name: COLUMN agent_verification_rules.expected; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_verification_rules.expected IS 'Interpreted per rule_type: "0" for exit_code, substring for grep/grep_not, absolute path for file_exists, URL for http_200, handler name for custom';


--
-- Name: COLUMN agent_verification_rules.on_fail; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_verification_rules.on_fail IS 'retry=same command again, fix=transition session to fixing phase, escalate=ask user, abort=mark session failed';


--
-- Name: COLUMN agent_verification_rules.priority; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.agent_verification_rules.priority IS 'Lower value = checked first when multiple rules match a command';


--
-- Name: agent_verification_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

ALTER TABLE public.agent_verification_rules ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.agent_verification_rules_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: archive_tags; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.archive_tags (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100),
    color character varying(7) DEFAULT '#C49A6C'::character varying,
    icon character varying(10) DEFAULT '·'::character varying,
    sort_order integer DEFAULT 50
);


ALTER TABLE public.archive_tags OWNER TO claude;

--
-- Name: archive_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.archive_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.archive_tags_id_seq OWNER TO claude;

--
-- Name: archive_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.archive_tags_id_seq OWNED BY public.archive_tags.id;


--
-- Name: artifacts; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.artifacts (
    id integer NOT NULL,
    project_id integer,
    name character varying(200) NOT NULL,
    description character varying(500),
    file_path character varying(500),
    content text,
    artifact_type character varying(50),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.artifacts OWNER TO claude;

--
-- Name: artifacts_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.artifacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.artifacts_id_seq OWNER TO claude;

--
-- Name: artifacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.artifacts_id_seq OWNED BY public.artifacts.id;


--
-- Name: authorizations; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.authorizations (
    id integer NOT NULL,
    job_id integer,
    operation text NOT NULL,
    details text,
    risk_level character varying(10) NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying,
    requested_at timestamp without time zone DEFAULT now(),
    decided_at timestamp without time zone
);


ALTER TABLE public.authorizations OWNER TO claude;

--
-- Name: authorizations_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.authorizations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.authorizations_id_seq OWNER TO claude;

--
-- Name: authorizations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.authorizations_id_seq OWNED BY public.authorizations.id;


--
-- Name: autonomy_config; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.autonomy_config (
    category character varying(50) NOT NULL,
    risk_level character varying(20) NOT NULL,
    auto_threshold double precision NOT NULL,
    window_size integer DEFAULT 20,
    notes text
);


ALTER TABLE public.autonomy_config OWNER TO claude;

--
-- Name: autonomy_rules; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.autonomy_rules (
    id integer NOT NULL,
    level integer NOT NULL,
    pattern character varying(200) NOT NULL,
    action character varying(20) NOT NULL,
    description text
);


ALTER TABLE public.autonomy_rules OWNER TO claude;

--
-- Name: autonomy_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.autonomy_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.autonomy_rules_id_seq OWNER TO claude;

--
-- Name: autonomy_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.autonomy_rules_id_seq OWNED BY public.autonomy_rules.id;


--
-- Name: calup_commands; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.calup_commands (
    id integer NOT NULL,
    calup_id integer,
    command_id integer,
    "position" integer NOT NULL,
    required boolean DEFAULT true
);


ALTER TABLE public.calup_commands OWNER TO claude;

--
-- Name: calup_commands_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.calup_commands_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.calup_commands_id_seq OWNER TO claude;

--
-- Name: calup_commands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.calup_commands_id_seq OWNED BY public.calup_commands.id;


--
-- Name: calup_scores; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.calup_scores (
    id integer NOT NULL,
    calup_name character varying(200),
    calup_hash character varying(64) NOT NULL,
    score integer DEFAULT 500,
    skill_id integer,
    status character varying(20) DEFAULT 'active'::character varying,
    fail_streak integer DEFAULT 0,
    unstable_threshold integer DEFAULT 3,
    os_type character varying(50),
    os_version character varying(50),
    last_used timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT calup_scores_score_check CHECK (((score >= 0) AND (score <= 1000))),
    CONSTRAINT calup_scores_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'unstable'::character varying, 'retired'::character varying])::text[])))
);


ALTER TABLE public.calup_scores OWNER TO claude;

--
-- Name: calup_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.calup_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.calup_scores_id_seq OWNER TO claude;

--
-- Name: calup_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.calup_scores_id_seq OWNED BY public.calup_scores.id;


--
-- Name: chat_scratchpad; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.chat_scratchpad (
    id bigint NOT NULL,
    conversation_id integer,
    session_key text,
    note_key text NOT NULL,
    note_value text NOT NULL,
    source character varying(30) DEFAULT 'uncertain'::character varying NOT NULL,
    confidence character varying(10) DEFAULT 'medium'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone,
    CONSTRAINT chat_scratchpad_confidence_check CHECK (((confidence)::text = ANY ((ARRAY['high'::character varying, 'medium'::character varying, 'low'::character varying])::text[]))),
    CONSTRAINT chat_scratchpad_source_check CHECK (((source)::text = ANY ((ARRAY['tested_live'::character varying, 'user_said'::character varying, 'from_skill'::character varying, 'computed'::character varying, 'uncertain'::character varying, 'db_query'::character varying])::text[]))),
    CONSTRAINT chk_scratchpad_owner CHECK (((conversation_id IS NOT NULL) OR (session_key IS NOT NULL)))
);


ALTER TABLE public.chat_scratchpad OWNER TO claude;

--
-- Name: TABLE chat_scratchpad; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON TABLE public.chat_scratchpad IS 'Anti-hallucination scratchpad - Claude takes notes per conversation, reads at start of each turn to avoid inventing facts';


--
-- Name: COLUMN chat_scratchpad.note_key; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.chat_scratchpad.note_key IS 'Structured key like verified_cmd:docker_ps, schema:agent_sessions, user_pref:short_answers';


--
-- Name: COLUMN chat_scratchpad.source; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.chat_scratchpad.source IS 'How this fact was obtained: tested_live=ran command live, user_said=user told us, from_skill=cited skill #X, computed=calculated from other facts, db_query=SELECT result, uncertain=guess marked';


--
-- Name: COLUMN chat_scratchpad.confidence; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.chat_scratchpad.confidence IS 'high=verified live multiple times, medium=single verification, low=uncertain or stale';


--
-- Name: COLUMN chat_scratchpad.expires_at; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.chat_scratchpad.expires_at IS 'Optional TTL for temporary facts (e.g. current process state) - NULL means permanent until session ends';


--
-- Name: chat_scratchpad_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

ALTER TABLE public.chat_scratchpad ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.chat_scratchpad_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: command_scores; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.command_scores (
    id integer NOT NULL,
    command text NOT NULL,
    command_hash character varying(64) NOT NULL,
    score integer DEFAULT 500,
    success_count integer DEFAULT 0,
    fail_count integer DEFAULT 0,
    os_type character varying(50),
    os_version character varying(50),
    context character varying(100),
    mission_complete boolean DEFAULT false,
    last_used timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    pinned boolean DEFAULT false,
    CONSTRAINT command_scores_score_check CHECK (((score >= 0) AND (score <= 1000)))
);


ALTER TABLE public.command_scores OWNER TO claude;

--
-- Name: command_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.command_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.command_scores_id_seq OWNER TO claude;

--
-- Name: command_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.command_scores_id_seq OWNED BY public.command_scores.id;


--
-- Name: file_index; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.file_index (
    id integer NOT NULL,
    file_path text NOT NULL,
    file_type character varying(20),
    zone character varying(100) NOT NULL,
    sub_zone character varying(100),
    parent_zone character varying(100),
    managed_by character varying(20) DEFAULT 'human'::character varying NOT NULL,
    critical boolean DEFAULT false,
    restart_required character varying(20),
    line_start integer,
    line_end integer,
    autonomy_level integer,
    tags jsonb DEFAULT '{}'::jsonb,
    description text,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.file_index OWNER TO claude;

--
-- Name: config_index; Type: VIEW; Schema: public; Owner: claude
--

CREATE VIEW public.config_index AS
 SELECT id,
    zone,
    managed_by,
    critical,
    restart_required,
    line_start,
    line_end,
    tags,
    description,
    updated_at
   FROM public.file_index
  WHERE (file_path = '/etc/nixos/configuration.nix'::text);


ALTER VIEW public.config_index OWNER TO claude;

--
-- Name: config_index_legacy; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.config_index_legacy (
    id integer NOT NULL,
    zone character varying(50) NOT NULL,
    managed_by character varying(20) NOT NULL,
    critical boolean DEFAULT false,
    restart_required character varying(20),
    line_start integer,
    line_end integer,
    tags jsonb,
    description text,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.config_index_legacy OWNER TO claude;

--
-- Name: config_index_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.config_index_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.config_index_id_seq OWNER TO claude;

--
-- Name: config_index_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.config_index_id_seq OWNED BY public.config_index_legacy.id;


--
-- Name: conversation_archives; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.conversation_archives (
    id integer NOT NULL,
    conversation_id integer,
    title character varying(200) NOT NULL,
    summary text,
    tags text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.conversation_archives OWNER TO claude;

--
-- Name: conversation_archives_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.conversation_archives_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.conversation_archives_id_seq OWNER TO claude;

--
-- Name: conversation_archives_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.conversation_archives_id_seq OWNED BY public.conversation_archives.id;


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.conversations (
    id integer NOT NULL,
    project_id integer,
    title character varying(200),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.conversations OWNER TO claude;

--
-- Name: conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.conversations_id_seq OWNER TO claude;

--
-- Name: conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.conversations_id_seq OWNED BY public.conversations.id;


--
-- Name: debug_logs; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.debug_logs (
    id integer NOT NULL,
    ts timestamp without time zone DEFAULT now(),
    level character varying(10) NOT NULL,
    module character varying(30) NOT NULL,
    code character varying(10) NOT NULL,
    message text NOT NULL,
    context jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE public.debug_logs OWNER TO claude;

--
-- Name: debug_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.debug_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.debug_logs_id_seq OWNER TO claude;

--
-- Name: debug_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.debug_logs_id_seq OWNED BY public.debug_logs.id;


--
-- Name: error_codes; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.error_codes (
    code character varying(5) NOT NULL,
    domain character varying(20) NOT NULL,
    title character varying(100) NOT NULL,
    description text NOT NULL,
    where_to_look text NOT NULL,
    protocol text NOT NULL,
    recovery_ref character varying(20),
    severity character varying(10) NOT NULL,
    file_path text,
    zone character varying(100),
    CONSTRAINT error_codes_severity_check CHECK (((severity)::text = ANY ((ARRAY['critical'::character varying, 'high'::character varying, 'medium'::character varying, 'low'::character varying])::text[])))
);


ALTER TABLE public.error_codes OWNER TO claude;

--
-- Name: error_history; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.error_history (
    hash character(8) NOT NULL,
    category character varying(64),
    summary text,
    node_hostname character varying(64),
    resolved_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.error_history OWNER TO claude;

--
-- Name: error_patterns; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.error_patterns (
    hash character(8) NOT NULL,
    pattern text NOT NULL,
    category character varying(64) NOT NULL,
    count integer DEFAULT 1,
    first_seen timestamp without time zone DEFAULT now(),
    last_seen timestamp without time zone DEFAULT now(),
    node_hostname character varying(64),
    node_os character varying(64),
    contexts jsonb DEFAULT '[]'::jsonb,
    client_owned boolean DEFAULT false,
    resolved boolean DEFAULT false
);


ALTER TABLE public.error_patterns OWNER TO claude;

--
-- Name: event_items; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.event_items (
    id integer NOT NULL,
    event_id integer NOT NULL,
    item text NOT NULL,
    quantity text,
    notes text,
    done boolean DEFAULT false,
    done_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.event_items OWNER TO claude;

--
-- Name: event_items_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.event_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.event_items_id_seq OWNER TO claude;

--
-- Name: event_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.event_items_id_seq OWNED BY public.event_items.id;


--
-- Name: events; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.events (
    id integer NOT NULL,
    title text NOT NULL,
    description text,
    place_id integer,
    target_id integer,
    when_estimated text,
    when_date date,
    status character varying(20) DEFAULT 'planned'::character varying,
    priority integer DEFAULT 3,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    done_at timestamp without time zone
);


ALTER TABLE public.events OWNER TO claude;

--
-- Name: events_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.events_id_seq OWNER TO claude;

--
-- Name: events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.events_id_seq OWNED BY public.events.id;


--
-- Name: file_index_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.file_index_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.file_index_id_seq OWNER TO claude;

--
-- Name: file_index_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.file_index_id_seq OWNED BY public.file_index.id;


--
-- Name: file_versions; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.file_versions (
    id integer NOT NULL,
    module_name character varying(100),
    version_type character varying(10) NOT NULL,
    content bytea NOT NULL,
    file_path text NOT NULL,
    hash character varying(64),
    created_at timestamp without time zone DEFAULT now(),
    created_by character varying(50) DEFAULT 'argos'::character varying
);


ALTER TABLE public.file_versions OWNER TO claude;

--
-- Name: file_versions_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.file_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.file_versions_id_seq OWNER TO claude;

--
-- Name: file_versions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.file_versions_id_seq OWNED BY public.file_versions.id;


--
-- Name: ha_automations; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.ha_automations (
    id integer NOT NULL,
    entity_id character varying(200) NOT NULL,
    friendly_name character varying(300),
    last_state character varying(50),
    last_seen timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.ha_automations OWNER TO claude;

--
-- Name: ha_automations_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.ha_automations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ha_automations_id_seq OWNER TO claude;

--
-- Name: ha_automations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.ha_automations_id_seq OWNED BY public.ha_automations.id;


--
-- Name: ha_devices; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.ha_devices (
    id integer NOT NULL,
    entity_id character varying(200) NOT NULL,
    friendly_name character varying(300),
    last_state character varying(50),
    source_type character varying(50),
    last_seen timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.ha_devices OWNER TO claude;

--
-- Name: ha_devices_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.ha_devices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ha_devices_id_seq OWNER TO claude;

--
-- Name: ha_devices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.ha_devices_id_seq OWNED BY public.ha_devices.id;


--
-- Name: ha_entities; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.ha_entities (
    id integer NOT NULL,
    entity_id character varying(200) NOT NULL,
    domain character varying(50),
    friendly_name character varying(300),
    last_state character varying(200),
    unit_of_measurement character varying(50),
    device_class character varying(100),
    last_changed timestamp with time zone,
    last_updated timestamp with time zone,
    last_seen timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.ha_entities OWNER TO claude;

--
-- Name: ha_entities_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.ha_entities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ha_entities_id_seq OWNER TO claude;

--
-- Name: ha_entities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.ha_entities_id_seq OWNED BY public.ha_entities.id;


--
-- Name: ha_integrations; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.ha_integrations (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    last_seen timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.ha_integrations OWNER TO claude;

--
-- Name: ha_integrations_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.ha_integrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ha_integrations_id_seq OWNER TO claude;

--
-- Name: ha_integrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.ha_integrations_id_seq OWNED BY public.ha_integrations.id;


--
-- Name: ha_scenes; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.ha_scenes (
    id integer NOT NULL,
    entity_id character varying(200) NOT NULL,
    friendly_name character varying(300),
    last_state character varying(200),
    last_seen timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.ha_scenes OWNER TO claude;

--
-- Name: ha_scenes_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.ha_scenes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ha_scenes_id_seq OWNER TO claude;

--
-- Name: ha_scenes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.ha_scenes_id_seq OWNED BY public.ha_scenes.id;


--
-- Name: heartbeat_checks; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.heartbeat_checks (
    id integer NOT NULL,
    component character varying(50) NOT NULL,
    check_name character varying(100) NOT NULL,
    display_name text NOT NULL,
    display_order integer DEFAULT 100,
    display_group character varying(50) DEFAULT 'General'::character varying NOT NULL,
    icon character varying(30),
    file_path text,
    zone character varying(100),
    query_sql text,
    history_query_sql text,
    unit character varying(20),
    threshold_ok jsonb,
    threshold_warn jsonb,
    threshold_crit jsonb,
    refresh_interval_sec integer DEFAULT 5,
    last_status character varying(20),
    last_value numeric,
    last_checked timestamp without time zone,
    enabled boolean DEFAULT true,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.heartbeat_checks OWNER TO claude;

--
-- Name: heartbeat_checks_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.heartbeat_checks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.heartbeat_checks_id_seq OWNER TO claude;

--
-- Name: heartbeat_checks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.heartbeat_checks_id_seq OWNED BY public.heartbeat_checks.id;


--
-- Name: heartbeat_log; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.heartbeat_log (
    id integer NOT NULL,
    node text NOT NULL,
    service text NOT NULL,
    status text NOT NULL,
    cpu_pct double precision,
    mem_pct double precision,
    db_latency_ms integer,
    containers_up integer,
    error_code text,
    error_msg text,
    ts timestamp without time zone DEFAULT now()
);


ALTER TABLE public.heartbeat_log OWNER TO claude;

--
-- Name: heartbeat_log_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.heartbeat_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.heartbeat_log_id_seq OWNER TO claude;

--
-- Name: heartbeat_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.heartbeat_log_id_seq OWNED BY public.heartbeat_log.id;


--
-- Name: indexed_files; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.indexed_files (
    id integer NOT NULL,
    file_path text NOT NULL,
    file_type character varying(20),
    auto_update boolean DEFAULT true,
    last_indexed timestamp without time zone,
    zones_count integer DEFAULT 0,
    notes text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.indexed_files OWNER TO claude;

--
-- Name: indexed_files_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.indexed_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.indexed_files_id_seq OWNER TO claude;

--
-- Name: indexed_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.indexed_files_id_seq OWNED BY public.indexed_files.id;


--
-- Name: iso_builds; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.iso_builds (
    id integer NOT NULL,
    iso_type_id integer,
    version integer NOT NULL,
    build_id character varying(16) NOT NULL,
    display_version character varying(20),
    params jsonb DEFAULT '{}'::jsonb NOT NULL,
    path_beasty character varying(200),
    path_proxmox character varying(200),
    proxmox_server_id integer,
    nix_config text,
    status character varying(20) DEFAULT 'building'::character varying,
    build_log text,
    error text,
    build_duration_seconds integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.iso_builds OWNER TO claude;

--
-- Name: iso_builds_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.iso_builds_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.iso_builds_id_seq OWNER TO claude;

--
-- Name: iso_builds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.iso_builds_id_seq OWNED BY public.iso_builds.id;


--
-- Name: iso_test_results; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.iso_test_results (
    id integer NOT NULL,
    build_id character varying(16),
    proxmox_server_id integer,
    test_vm_id integer,
    test_vm_ip character varying(15),
    announced boolean DEFAULT false,
    announce_time_seconds integer,
    boot_success boolean DEFAULT false,
    ssh_success boolean DEFAULT false,
    test_commands jsonb DEFAULT '[]'::jsonb,
    error text,
    log_excerpt text,
    tested_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.iso_test_results OWNER TO claude;

--
-- Name: iso_test_results_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.iso_test_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.iso_test_results_id_seq OWNER TO claude;

--
-- Name: iso_test_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.iso_test_results_id_seq OWNED BY public.iso_test_results.id;


--
-- Name: iso_types; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.iso_types (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100),
    category character varying(30) NOT NULL,
    purpose character varying(50) NOT NULL,
    description text,
    default_packages text[],
    default_services text[],
    default_params jsonb DEFAULT '{}'::jsonb,
    version_counter integer DEFAULT 0,
    active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.iso_types OWNER TO claude;

--
-- Name: iso_types_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.iso_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.iso_types_id_seq OWNER TO claude;

--
-- Name: iso_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.iso_types_id_seq OWNED BY public.iso_types.id;


--
-- Name: jobs; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.jobs (
    id integer NOT NULL,
    conversation_id integer,
    title text,
    status character varying(20) DEFAULT 'pending'::character varying,
    segments jsonb DEFAULT '[]'::jsonb NOT NULL,
    current_segment integer DEFAULT 0,
    results jsonb DEFAULT '[]'::jsonb,
    error text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.jobs OWNER TO claude;

--
-- Name: jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.jobs_id_seq OWNER TO claude;

--
-- Name: jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.jobs_id_seq OWNED BY public.jobs.id;


--
-- Name: knowledge_base; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.knowledge_base (
    id integer NOT NULL,
    category character varying(30) NOT NULL,
    iso_type_id integer,
    build_id character varying(16),
    action text NOT NULL,
    context jsonb DEFAULT '{}'::jsonb,
    outcome character varying(10) NOT NULL,
    reason text,
    skip boolean DEFAULT false,
    skip_reason text,
    times_tried integer DEFAULT 1,
    last_tried_at timestamp without time zone DEFAULT now(),
    created_at timestamp without time zone DEFAULT now(),
    os_type character varying(30),
    os_version character varying(30),
    command_type character varying(30),
    tested_on_version character varying(30),
    success_rate double precision DEFAULT 1.0
);


ALTER TABLE public.knowledge_base OWNER TO claude;

--
-- Name: COLUMN knowledge_base.os_type; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.knowledge_base.os_type IS 'unifi, nixos, debian, proxmox, windows, etc';


--
-- Name: COLUMN knowledge_base.os_version; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.knowledge_base.os_version IS 'versiunea exacta testata';


--
-- Name: COLUMN knowledge_base.command_type; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.knowledge_base.command_type IS 'api, ssh, bash, nix, systemd, etc';


--
-- Name: COLUMN knowledge_base.tested_on_version; Type: COMMENT; Schema: public; Owner: claude
--

COMMENT ON COLUMN public.knowledge_base.tested_on_version IS 'versiunea pe care s-a testat ultima oara';


--
-- Name: knowledge_base_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.knowledge_base_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.knowledge_base_id_seq OWNER TO claude;

--
-- Name: knowledge_base_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.knowledge_base_id_seq OWNED BY public.knowledge_base.id;


--
-- Name: lab_changelog; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.lab_changelog (
    id integer NOT NULL,
    action text NOT NULL,
    machine text,
    description text NOT NULL,
    files_modified text[],
    idea_id integer,
    impl_id integer,
    success boolean,
    notes text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.lab_changelog OWNER TO claude;

--
-- Name: lab_changelog_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.lab_changelog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lab_changelog_id_seq OWNER TO claude;

--
-- Name: lab_changelog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.lab_changelog_id_seq OWNED BY public.lab_changelog.id;


--
-- Name: lab_decisions; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.lab_decisions (
    id integer NOT NULL,
    title text NOT NULL,
    context text NOT NULL,
    decision text NOT NULL,
    reasoning text NOT NULL,
    alternatives jsonb,
    outcome text,
    status text DEFAULT 'active'::text,
    superseded_by integer,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.lab_decisions OWNER TO claude;

--
-- Name: lab_decisions_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.lab_decisions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lab_decisions_id_seq OWNER TO claude;

--
-- Name: lab_decisions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.lab_decisions_id_seq OWNED BY public.lab_decisions.id;


--
-- Name: lab_discussions; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.lab_discussions (
    id integer NOT NULL,
    idea_id integer,
    parent_id integer,
    author text NOT NULL,
    message text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.lab_discussions OWNER TO claude;

--
-- Name: lab_discussions_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.lab_discussions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lab_discussions_id_seq OWNER TO claude;

--
-- Name: lab_discussions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.lab_discussions_id_seq OWNED BY public.lab_discussions.id;


--
-- Name: lab_experiments; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.lab_experiments (
    id integer NOT NULL,
    idea_id integer,
    title text NOT NULL,
    hypothesis text NOT NULL,
    method text NOT NULL,
    result text,
    verdict text,
    learnings text,
    status text DEFAULT 'planned'::text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.lab_experiments OWNER TO claude;

--
-- Name: lab_experiments_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.lab_experiments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lab_experiments_id_seq OWNER TO claude;

--
-- Name: lab_experiments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.lab_experiments_id_seq OWNED BY public.lab_experiments.id;


--
-- Name: lab_fragments; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.lab_fragments (
    id integer NOT NULL,
    topic text NOT NULL,
    content text NOT NULL,
    source text,
    promote_to_skill boolean DEFAULT false,
    tags text[],
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.lab_fragments OWNER TO claude;

--
-- Name: lab_fragments_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.lab_fragments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lab_fragments_id_seq OWNER TO claude;

--
-- Name: lab_fragments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.lab_fragments_id_seq OWNED BY public.lab_fragments.id;


--
-- Name: lab_ideas; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.lab_ideas (
    id integer NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    origin text DEFAULT 'user'::text,
    status text DEFAULT 'raw'::text,
    priority integer DEFAULT 3,
    tags text[],
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.lab_ideas OWNER TO claude;

--
-- Name: lab_ideas_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.lab_ideas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lab_ideas_id_seq OWNER TO claude;

--
-- Name: lab_ideas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.lab_ideas_id_seq OWNED BY public.lab_ideas.id;


--
-- Name: lab_implementations; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.lab_implementations (
    id integer NOT NULL,
    idea_id integer,
    title text NOT NULL,
    description text NOT NULL,
    steps jsonb,
    status text DEFAULT 'planned'::text,
    machine text,
    blockers text,
    result text,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.lab_implementations OWNER TO claude;

--
-- Name: lab_implementations_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.lab_implementations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lab_implementations_id_seq OWNER TO claude;

--
-- Name: lab_implementations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.lab_implementations_id_seq OWNED BY public.lab_implementations.id;


--
-- Name: log_entries; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.log_entries (
    id integer NOT NULL,
    type character varying(10) DEFAULT 'info'::character varying NOT NULL,
    message text NOT NULL,
    conversation_id integer,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.log_entries OWNER TO claude;

--
-- Name: log_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.log_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.log_entries_id_seq OWNER TO claude;

--
-- Name: log_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.log_entries_id_seq OWNED BY public.log_entries.id;


--
-- Name: memories; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.memories (
    id integer NOT NULL,
    project_id integer,
    key character varying(200) NOT NULL,
    value text NOT NULL,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.memories OWNER TO claude;

--
-- Name: memories_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.memories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.memories_id_seq OWNER TO claude;

--
-- Name: memories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.memories_id_seq OWNED BY public.memories.id;


--
-- Name: messages; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.messages (
    id integer NOT NULL,
    conversation_id integer,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    tokens_input integer,
    tokens_output integer,
    cost_eur numeric(10,6),
    created_at timestamp without time zone DEFAULT now(),
    pending boolean DEFAULT false
);


ALTER TABLE public.messages OWNER TO claude;

--
-- Name: messages_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.messages_id_seq OWNER TO claude;

--
-- Name: messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.messages_id_seq OWNED BY public.messages.id;


--
-- Name: module_preferences; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.module_preferences (
    id integer NOT NULL,
    pattern text NOT NULL,
    modules text[] NOT NULL,
    confirmed_by_user boolean DEFAULT false,
    times_used integer DEFAULT 1,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.module_preferences OWNER TO claude;

--
-- Name: module_preferences_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.module_preferences_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.module_preferences_id_seq OWNER TO claude;

--
-- Name: module_preferences_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.module_preferences_id_seq OWNED BY public.module_preferences.id;


--
-- Name: nanite_commands; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.nanite_commands (
    id integer NOT NULL,
    node_id character varying(20) NOT NULL,
    command text NOT NULL,
    timeout integer DEFAULT 120,
    status character varying(20) DEFAULT 'pending'::character varying,
    returncode integer,
    stdout text,
    stderr text,
    created_at timestamp without time zone DEFAULT now(),
    sent_at timestamp without time zone,
    finished_at timestamp without time zone
);


ALTER TABLE public.nanite_commands OWNER TO claude;

--
-- Name: nanite_commands_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.nanite_commands_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.nanite_commands_id_seq OWNER TO claude;

--
-- Name: nanite_commands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.nanite_commands_id_seq OWNED BY public.nanite_commands.id;


--
-- Name: nanite_nodes; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.nanite_nodes (
    id integer NOT NULL,
    node_id character varying(20) NOT NULL,
    ip character varying(15) NOT NULL,
    status character varying(20) DEFAULT 'announced'::character varying,
    cpu_model character varying(200),
    cpu_cores integer,
    cpu_threads integer,
    ram_mb integer,
    disks jsonb DEFAULT '[]'::jsonb,
    gpu character varying(200),
    network_interfaces jsonb DEFAULT '[]'::jsonb,
    usb_devices jsonb DEFAULT '[]'::jsonb,
    pci_devices jsonb DEFAULT '[]'::jsonb,
    arch character varying(20),
    uefi boolean DEFAULT true,
    hostname character varying(100),
    nanite_version character varying(20),
    build_id character varying(16),
    announced_at timestamp without time zone DEFAULT now(),
    last_seen timestamp without time zone DEFAULT now(),
    install_started_at timestamp without time zone,
    install_finished_at timestamp without time zone,
    install_profile character varying(50),
    install_log text,
    installed_system_id integer,
    notes text,
    extra jsonb DEFAULT '{}'::jsonb,
    tailscale_ip character varying(45),
    tailscale_name character varying(100)
);


ALTER TABLE public.nanite_nodes OWNER TO claude;

--
-- Name: nanite_nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.nanite_nodes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.nanite_nodes_id_seq OWNER TO claude;

--
-- Name: nanite_nodes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.nanite_nodes_id_seq OWNED BY public.nanite_nodes.id;


--
-- Name: notes; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.notes (
    id integer NOT NULL,
    category character varying(50) DEFAULT 'general'::character varying,
    content text NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying,
    priority integer DEFAULT 5,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    done_at timestamp without time zone,
    public boolean DEFAULT false,
    target_id integer,
    place_id integer,
    event_id integer
);


ALTER TABLE public.notes OWNER TO claude;

--
-- Name: notes_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.notes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notes_id_seq OWNER TO claude;

--
-- Name: notes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.notes_id_seq OWNED BY public.notes.id;


--
-- Name: place_relations; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.place_relations (
    id integer NOT NULL,
    from_place_id integer NOT NULL,
    to_place_id integer NOT NULL,
    relation_type character varying(30) NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.place_relations OWNER TO claude;

--
-- Name: place_relations_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.place_relations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.place_relations_id_seq OWNER TO claude;

--
-- Name: place_relations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.place_relations_id_seq OWNED BY public.place_relations.id;


--
-- Name: places; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.places (
    id integer NOT NULL,
    name text NOT NULL,
    type character varying(50),
    lat numeric(9,6),
    lon numeric(9,6),
    address text,
    city text,
    country text,
    metadata jsonb DEFAULT '{}'::jsonb,
    source character varying(30) DEFAULT 'manual'::character varying,
    confirmed boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.places OWNER TO claude;

--
-- Name: places_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.places_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.places_id_seq OWNER TO claude;

--
-- Name: places_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.places_id_seq OWNED BY public.places.id;


--
-- Name: playbooks; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.playbooks (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    trigger_type character varying(20) DEFAULT 'manual'::character varying,
    steps jsonb DEFAULT '[]'::jsonb NOT NULL,
    requires_confirmation boolean DEFAULT false,
    active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT playbooks_trigger_type_check CHECK (((trigger_type)::text = ANY ((ARRAY['manual'::character varying, 'automatic'::character varying, 'condition'::character varying])::text[])))
);


ALTER TABLE public.playbooks OWNER TO claude;

--
-- Name: playbooks_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.playbooks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.playbooks_id_seq OWNER TO claude;

--
-- Name: playbooks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.playbooks_id_seq OWNED BY public.playbooks.id;


--
-- Name: procedures; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.procedures (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    category character varying(50),
    steps jsonb NOT NULL,
    requires_backup boolean DEFAULT false,
    requires_vm_test boolean DEFAULT false,
    apply_at_night boolean DEFAULT false,
    requires_confirmation boolean DEFAULT false,
    active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT procedures_category_check CHECK (((category)::text = ANY ((ARRAY['scout'::character varying, 'engineer'::character varying, 'commander'::character varying, 'warlord'::character varying])::text[])))
);


ALTER TABLE public.procedures OWNER TO claude;

--
-- Name: procedures_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.procedures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.procedures_id_seq OWNER TO claude;

--
-- Name: procedures_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.procedures_id_seq OWNED BY public.procedures.id;


--
-- Name: projects; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.projects (
    id integer NOT NULL,
    parent_id integer,
    name character varying(100) NOT NULL,
    description character varying(500),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.projects OWNER TO claude;

--
-- Name: projects_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.projects_id_seq OWNER TO claude;

--
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.projects_id_seq OWNED BY public.projects.id;


--
-- Name: prompt_modules; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.prompt_modules (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    category character varying(30) NOT NULL,
    display_name character varying(100),
    content text NOT NULL,
    keywords text[] DEFAULT '{}'::text[] NOT NULL,
    priority integer DEFAULT 50,
    active boolean DEFAULT true,
    version integer DEFAULT 1,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.prompt_modules OWNER TO claude;

--
-- Name: prompt_modules_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.prompt_modules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.prompt_modules_id_seq OWNER TO claude;

--
-- Name: prompt_modules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.prompt_modules_id_seq OWNED BY public.prompt_modules.id;


--
-- Name: proxmox_servers; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.proxmox_servers (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100),
    ip character varying(15) NOT NULL,
    ssh_user character varying(50) DEFAULT 'root'::character varying,
    iso_path character varying(200) DEFAULT '/var/lib/vz/template/iso'::character varying,
    is_default boolean DEFAULT false,
    notes text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.proxmox_servers OWNER TO claude;

--
-- Name: proxmox_servers_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.proxmox_servers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.proxmox_servers_id_seq OWNER TO claude;

--
-- Name: proxmox_servers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.proxmox_servers_id_seq OWNED BY public.proxmox_servers.id;


--
-- Name: reasoning_axioms; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.reasoning_axioms (
    id integer NOT NULL,
    domain character varying(50) NOT NULL,
    content text NOT NULL,
    active boolean DEFAULT true,
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.reasoning_axioms OWNER TO claude;

--
-- Name: reasoning_axioms_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.reasoning_axioms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reasoning_axioms_id_seq OWNER TO claude;

--
-- Name: reasoning_axioms_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.reasoning_axioms_id_seq OWNED BY public.reasoning_axioms.id;


--
-- Name: reasoning_log; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.reasoning_log (
    id integer NOT NULL,
    conversation_id integer,
    type text NOT NULL,
    content text NOT NULL,
    ts timestamp without time zone DEFAULT now()
);


ALTER TABLE public.reasoning_log OWNER TO claude;

--
-- Name: reasoning_log_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.reasoning_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reasoning_log_id_seq OWNER TO claude;

--
-- Name: reasoning_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.reasoning_log_id_seq OWNED BY public.reasoning_log.id;


--
-- Name: segments; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.segments (
    id integer NOT NULL,
    conversation_id integer,
    summary text NOT NULL,
    message_start_id integer,
    message_end_id integer,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.segments OWNER TO claude;

--
-- Name: segments_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.segments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.segments_id_seq OWNER TO claude;

--
-- Name: segments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.segments_id_seq OWNED BY public.segments.id;


--
-- Name: settings; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.settings (
    key character varying(50) NOT NULL,
    value text,
    updated_at timestamp without time zone DEFAULT now(),
    value_type character varying(20),
    description text,
    updated_by character varying(50),
    auto_update boolean DEFAULT false,
    hint_query text
);


ALTER TABLE public.settings OWNER TO claude;

--
-- Name: skills; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.skills (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    filename character varying(200) NOT NULL,
    os_type character varying(50),
    version character varying(50),
    keywords text[],
    loaded_when text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.skills OWNER TO claude;

--
-- Name: skills_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.skills_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.skills_id_seq OWNER TO claude;

--
-- Name: skills_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.skills_id_seq OWNED BY public.skills.id;


--
-- Name: skills_tree; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.skills_tree (
    id bigint NOT NULL,
    path character varying(200) NOT NULL,
    parent_path character varying(200),
    name character varying(200) NOT NULL,
    tags text[] DEFAULT '{}'::text[],
    source character varying(10) DEFAULT 'manual'::character varying,
    emergency boolean DEFAULT false,
    usage_count integer DEFAULT 0,
    last_used timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    content text NOT NULL,
    verified boolean DEFAULT false,
    verified_at timestamp without time zone,
    verified_by character varying(50),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT skills_tree_source_check CHECK (((source)::text = ANY (ARRAY[('manual'::character varying)::text, ('auto'::character varying)::text])))
);


ALTER TABLE public.skills_tree OWNER TO claude;

--
-- Name: system_credentials; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.system_credentials (
    id integer NOT NULL,
    system_id integer,
    credential_type character varying(30) NOT NULL,
    label character varying(100) NOT NULL,
    username character varying(100),
    value_hint character varying(50),
    notes text,
    active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.system_credentials OWNER TO claude;

--
-- Name: system_credentials_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.system_credentials_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.system_credentials_id_seq OWNER TO claude;

--
-- Name: system_credentials_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.system_credentials_id_seq OWNED BY public.system_credentials.id;


--
-- Name: system_modules; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.system_modules (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    module_type character varying(50) NOT NULL,
    file_path text,
    last_known_good_hash character varying(64),
    last_known_good_at timestamp without time zone,
    backup_path text,
    status character varying(20) DEFAULT 'unknown'::character varying,
    health_check_cmd text,
    checked_at timestamp without time zone
);


ALTER TABLE public.system_modules OWNER TO claude;

--
-- Name: system_modules_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.system_modules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.system_modules_id_seq OWNER TO claude;

--
-- Name: system_modules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.system_modules_id_seq OWNED BY public.system_modules.id;


--
-- Name: system_profiles; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.system_profiles (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100),
    owner character varying(50),
    os_type character varying(30),
    os_version character varying(30),
    hostname character varying(100),
    ip character varying(15),
    cpu character varying(100),
    ram_gb integer,
    storage text,
    gpu character varying(100),
    location character varying(100),
    role character varying(50),
    purpose text,
    prompt_modules text[],
    notes text,
    active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    nanite_node_id character varying(20),
    online boolean DEFAULT false,
    last_seen timestamp without time zone
);


ALTER TABLE public.system_profiles OWNER TO claude;

--
-- Name: system_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.system_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.system_profiles_id_seq OWNER TO claude;

--
-- Name: system_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.system_profiles_id_seq OWNED BY public.system_profiles.id;


--
-- Name: targets; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.targets (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.targets OWNER TO claude;

--
-- Name: targets_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.targets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.targets_id_seq OWNER TO claude;

--
-- Name: targets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.targets_id_seq OWNED BY public.targets.id;


--
-- Name: tool_scores; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.tool_scores (
    id integer NOT NULL,
    tool_name character varying(50) NOT NULL,
    task_type character varying(50) DEFAULT 'general'::character varying,
    success_count integer DEFAULT 0,
    fail_count integer DEFAULT 0,
    avg_duration_ms integer DEFAULT 0,
    last_used timestamp without time zone DEFAULT now()
);


ALTER TABLE public.tool_scores OWNER TO claude;

--
-- Name: tool_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.tool_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tool_scores_id_seq OWNER TO claude;

--
-- Name: tool_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.tool_scores_id_seq OWNED BY public.tool_scores.id;


--
-- Name: working_memory; Type: TABLE; Schema: public; Owner: claude
--

CREATE TABLE public.working_memory (
    id integer NOT NULL,
    conversation_id integer,
    task_current text,
    steps_done jsonb DEFAULT '[]'::jsonb,
    steps_planned jsonb DEFAULT '[]'::jsonb,
    status character varying(20) DEFAULT 'active'::character varying,
    started_at timestamp without time zone DEFAULT now(),
    last_update timestamp without time zone DEFAULT now()
);


ALTER TABLE public.working_memory OWNER TO claude;

--
-- Name: working_memory_id_seq; Type: SEQUENCE; Schema: public; Owner: claude
--

CREATE SEQUENCE public.working_memory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.working_memory_id_seq OWNER TO claude;

--
-- Name: working_memory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: claude
--

ALTER SEQUENCE public.working_memory_id_seq OWNED BY public.working_memory.id;


--
-- Name: credentials id; Type: DEFAULT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.credentials ALTER COLUMN id SET DEFAULT nextval('cristin.credentials_id_seq'::regclass);


--
-- Name: device_history id; Type: DEFAULT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.device_history ALTER COLUMN id SET DEFAULT nextval('cristin.device_history_id_seq'::regclass);


--
-- Name: devices id; Type: DEFAULT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.devices ALTER COLUMN id SET DEFAULT nextval('cristin.devices_id_seq'::regclass);


--
-- Name: events id; Type: DEFAULT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.events ALTER COLUMN id SET DEFAULT nextval('cristin.events_id_seq'::regclass);


--
-- Name: network_snapshots id; Type: DEFAULT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.network_snapshots ALTER COLUMN id SET DEFAULT nextval('cristin.network_snapshots_id_seq'::regclass);


--
-- Name: decisions id; Type: DEFAULT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.decisions ALTER COLUMN id SET DEFAULT nextval('lab.decisions_id_seq'::regclass);


--
-- Name: discussions id; Type: DEFAULT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.discussions ALTER COLUMN id SET DEFAULT nextval('lab.discussions_id_seq'::regclass);


--
-- Name: ideas id; Type: DEFAULT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.ideas ALTER COLUMN id SET DEFAULT nextval('lab.ideas_id_seq'::regclass);


--
-- Name: implementations id; Type: DEFAULT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.implementations ALTER COLUMN id SET DEFAULT nextval('lab.implementations_id_seq'::regclass);


--
-- Name: archive_tags id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.archive_tags ALTER COLUMN id SET DEFAULT nextval('public.archive_tags_id_seq'::regclass);


--
-- Name: artifacts id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.artifacts ALTER COLUMN id SET DEFAULT nextval('public.artifacts_id_seq'::regclass);


--
-- Name: authorizations id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.authorizations ALTER COLUMN id SET DEFAULT nextval('public.authorizations_id_seq'::regclass);


--
-- Name: autonomy_rules id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.autonomy_rules ALTER COLUMN id SET DEFAULT nextval('public.autonomy_rules_id_seq'::regclass);


--
-- Name: calup_commands id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.calup_commands ALTER COLUMN id SET DEFAULT nextval('public.calup_commands_id_seq'::regclass);


--
-- Name: calup_scores id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.calup_scores ALTER COLUMN id SET DEFAULT nextval('public.calup_scores_id_seq'::regclass);


--
-- Name: command_scores id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.command_scores ALTER COLUMN id SET DEFAULT nextval('public.command_scores_id_seq'::regclass);


--
-- Name: config_index_legacy id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.config_index_legacy ALTER COLUMN id SET DEFAULT nextval('public.config_index_id_seq'::regclass);


--
-- Name: conversation_archives id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.conversation_archives ALTER COLUMN id SET DEFAULT nextval('public.conversation_archives_id_seq'::regclass);


--
-- Name: conversations id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.conversations ALTER COLUMN id SET DEFAULT nextval('public.conversations_id_seq'::regclass);


--
-- Name: debug_logs id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.debug_logs ALTER COLUMN id SET DEFAULT nextval('public.debug_logs_id_seq'::regclass);


--
-- Name: event_items id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.event_items ALTER COLUMN id SET DEFAULT nextval('public.event_items_id_seq'::regclass);


--
-- Name: events id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.events ALTER COLUMN id SET DEFAULT nextval('public.events_id_seq'::regclass);


--
-- Name: file_index id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.file_index ALTER COLUMN id SET DEFAULT nextval('public.file_index_id_seq'::regclass);


--
-- Name: file_versions id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.file_versions ALTER COLUMN id SET DEFAULT nextval('public.file_versions_id_seq'::regclass);


--
-- Name: ha_automations id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_automations ALTER COLUMN id SET DEFAULT nextval('public.ha_automations_id_seq'::regclass);


--
-- Name: ha_devices id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_devices ALTER COLUMN id SET DEFAULT nextval('public.ha_devices_id_seq'::regclass);


--
-- Name: ha_entities id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_entities ALTER COLUMN id SET DEFAULT nextval('public.ha_entities_id_seq'::regclass);


--
-- Name: ha_integrations id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_integrations ALTER COLUMN id SET DEFAULT nextval('public.ha_integrations_id_seq'::regclass);


--
-- Name: ha_scenes id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_scenes ALTER COLUMN id SET DEFAULT nextval('public.ha_scenes_id_seq'::regclass);


--
-- Name: heartbeat_checks id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.heartbeat_checks ALTER COLUMN id SET DEFAULT nextval('public.heartbeat_checks_id_seq'::regclass);


--
-- Name: heartbeat_log id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.heartbeat_log ALTER COLUMN id SET DEFAULT nextval('public.heartbeat_log_id_seq'::regclass);


--
-- Name: indexed_files id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.indexed_files ALTER COLUMN id SET DEFAULT nextval('public.indexed_files_id_seq'::regclass);


--
-- Name: iso_builds id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_builds ALTER COLUMN id SET DEFAULT nextval('public.iso_builds_id_seq'::regclass);


--
-- Name: iso_test_results id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_test_results ALTER COLUMN id SET DEFAULT nextval('public.iso_test_results_id_seq'::regclass);


--
-- Name: iso_types id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_types ALTER COLUMN id SET DEFAULT nextval('public.iso_types_id_seq'::regclass);


--
-- Name: jobs id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.jobs ALTER COLUMN id SET DEFAULT nextval('public.jobs_id_seq'::regclass);


--
-- Name: knowledge_base id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.knowledge_base ALTER COLUMN id SET DEFAULT nextval('public.knowledge_base_id_seq'::regclass);


--
-- Name: lab_changelog id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_changelog ALTER COLUMN id SET DEFAULT nextval('public.lab_changelog_id_seq'::regclass);


--
-- Name: lab_decisions id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_decisions ALTER COLUMN id SET DEFAULT nextval('public.lab_decisions_id_seq'::regclass);


--
-- Name: lab_discussions id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_discussions ALTER COLUMN id SET DEFAULT nextval('public.lab_discussions_id_seq'::regclass);


--
-- Name: lab_experiments id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_experiments ALTER COLUMN id SET DEFAULT nextval('public.lab_experiments_id_seq'::regclass);


--
-- Name: lab_fragments id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_fragments ALTER COLUMN id SET DEFAULT nextval('public.lab_fragments_id_seq'::regclass);


--
-- Name: lab_ideas id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_ideas ALTER COLUMN id SET DEFAULT nextval('public.lab_ideas_id_seq'::regclass);


--
-- Name: lab_implementations id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_implementations ALTER COLUMN id SET DEFAULT nextval('public.lab_implementations_id_seq'::regclass);


--
-- Name: log_entries id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.log_entries ALTER COLUMN id SET DEFAULT nextval('public.log_entries_id_seq'::regclass);


--
-- Name: memories id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.memories ALTER COLUMN id SET DEFAULT nextval('public.memories_id_seq'::regclass);


--
-- Name: messages id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.messages ALTER COLUMN id SET DEFAULT nextval('public.messages_id_seq'::regclass);


--
-- Name: module_preferences id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.module_preferences ALTER COLUMN id SET DEFAULT nextval('public.module_preferences_id_seq'::regclass);


--
-- Name: nanite_commands id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.nanite_commands ALTER COLUMN id SET DEFAULT nextval('public.nanite_commands_id_seq'::regclass);


--
-- Name: nanite_nodes id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.nanite_nodes ALTER COLUMN id SET DEFAULT nextval('public.nanite_nodes_id_seq'::regclass);


--
-- Name: notes id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.notes ALTER COLUMN id SET DEFAULT nextval('public.notes_id_seq'::regclass);


--
-- Name: place_relations id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.place_relations ALTER COLUMN id SET DEFAULT nextval('public.place_relations_id_seq'::regclass);


--
-- Name: places id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.places ALTER COLUMN id SET DEFAULT nextval('public.places_id_seq'::regclass);


--
-- Name: playbooks id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.playbooks ALTER COLUMN id SET DEFAULT nextval('public.playbooks_id_seq'::regclass);


--
-- Name: procedures id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.procedures ALTER COLUMN id SET DEFAULT nextval('public.procedures_id_seq'::regclass);


--
-- Name: projects id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.projects ALTER COLUMN id SET DEFAULT nextval('public.projects_id_seq'::regclass);


--
-- Name: prompt_modules id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.prompt_modules ALTER COLUMN id SET DEFAULT nextval('public.prompt_modules_id_seq'::regclass);


--
-- Name: proxmox_servers id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.proxmox_servers ALTER COLUMN id SET DEFAULT nextval('public.proxmox_servers_id_seq'::regclass);


--
-- Name: reasoning_axioms id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.reasoning_axioms ALTER COLUMN id SET DEFAULT nextval('public.reasoning_axioms_id_seq'::regclass);


--
-- Name: reasoning_log id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.reasoning_log ALTER COLUMN id SET DEFAULT nextval('public.reasoning_log_id_seq'::regclass);


--
-- Name: segments id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.segments ALTER COLUMN id SET DEFAULT nextval('public.segments_id_seq'::regclass);


--
-- Name: skills id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.skills ALTER COLUMN id SET DEFAULT nextval('public.skills_id_seq'::regclass);


--
-- Name: system_credentials id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.system_credentials ALTER COLUMN id SET DEFAULT nextval('public.system_credentials_id_seq'::regclass);


--
-- Name: system_modules id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.system_modules ALTER COLUMN id SET DEFAULT nextval('public.system_modules_id_seq'::regclass);


--
-- Name: system_profiles id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.system_profiles ALTER COLUMN id SET DEFAULT nextval('public.system_profiles_id_seq'::regclass);


--
-- Name: targets id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.targets ALTER COLUMN id SET DEFAULT nextval('public.targets_id_seq'::regclass);


--
-- Name: tool_scores id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.tool_scores ALTER COLUMN id SET DEFAULT nextval('public.tool_scores_id_seq'::regclass);


--
-- Name: working_memory id; Type: DEFAULT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.working_memory ALTER COLUMN id SET DEFAULT nextval('public.working_memory_id_seq'::regclass);


--
-- Name: credentials credentials_pkey; Type: CONSTRAINT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.credentials
    ADD CONSTRAINT credentials_pkey PRIMARY KEY (id);


--
-- Name: device_history device_history_pkey; Type: CONSTRAINT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.device_history
    ADD CONSTRAINT device_history_pkey PRIMARY KEY (id);


--
-- Name: devices devices_mac_key; Type: CONSTRAINT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.devices
    ADD CONSTRAINT devices_mac_key UNIQUE (mac);


--
-- Name: devices devices_pkey; Type: CONSTRAINT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.devices
    ADD CONSTRAINT devices_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: network_snapshots network_snapshots_pkey; Type: CONSTRAINT; Schema: cristin; Owner: claude
--

ALTER TABLE ONLY cristin.network_snapshots
    ADD CONSTRAINT network_snapshots_pkey PRIMARY KEY (id);


--
-- Name: decisions decisions_pkey; Type: CONSTRAINT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.decisions
    ADD CONSTRAINT decisions_pkey PRIMARY KEY (id);


--
-- Name: discussions discussions_pkey; Type: CONSTRAINT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.discussions
    ADD CONSTRAINT discussions_pkey PRIMARY KEY (id);


--
-- Name: ideas ideas_pkey; Type: CONSTRAINT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.ideas
    ADD CONSTRAINT ideas_pkey PRIMARY KEY (id);


--
-- Name: implementations implementations_pkey; Type: CONSTRAINT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.implementations
    ADD CONSTRAINT implementations_pkey PRIMARY KEY (id);


--
-- Name: agent_sessions agent_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.agent_sessions
    ADD CONSTRAINT agent_sessions_pkey PRIMARY KEY (id);


--
-- Name: agent_verification_rules agent_verification_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.agent_verification_rules
    ADD CONSTRAINT agent_verification_rules_pkey PRIMARY KEY (id);


--
-- Name: archive_tags archive_tags_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.archive_tags
    ADD CONSTRAINT archive_tags_name_key UNIQUE (name);


--
-- Name: archive_tags archive_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.archive_tags
    ADD CONSTRAINT archive_tags_pkey PRIMARY KEY (id);


--
-- Name: artifacts artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.artifacts
    ADD CONSTRAINT artifacts_pkey PRIMARY KEY (id);


--
-- Name: authorizations authorizations_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.authorizations
    ADD CONSTRAINT authorizations_pkey PRIMARY KEY (id);


--
-- Name: autonomy_config autonomy_config_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.autonomy_config
    ADD CONSTRAINT autonomy_config_pkey PRIMARY KEY (category);


--
-- Name: autonomy_rules autonomy_rules_level_pattern_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.autonomy_rules
    ADD CONSTRAINT autonomy_rules_level_pattern_key UNIQUE (level, pattern);


--
-- Name: autonomy_rules autonomy_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.autonomy_rules
    ADD CONSTRAINT autonomy_rules_pkey PRIMARY KEY (id);


--
-- Name: calup_commands calup_commands_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.calup_commands
    ADD CONSTRAINT calup_commands_pkey PRIMARY KEY (id);


--
-- Name: calup_scores calup_scores_calup_hash_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.calup_scores
    ADD CONSTRAINT calup_scores_calup_hash_key UNIQUE (calup_hash);


--
-- Name: calup_scores calup_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.calup_scores
    ADD CONSTRAINT calup_scores_pkey PRIMARY KEY (id);


--
-- Name: chat_scratchpad chat_scratchpad_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.chat_scratchpad
    ADD CONSTRAINT chat_scratchpad_pkey PRIMARY KEY (id);


--
-- Name: command_scores command_scores_command_hash_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.command_scores
    ADD CONSTRAINT command_scores_command_hash_key UNIQUE (command_hash);


--
-- Name: command_scores command_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.command_scores
    ADD CONSTRAINT command_scores_pkey PRIMARY KEY (id);


--
-- Name: config_index_legacy config_index_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.config_index_legacy
    ADD CONSTRAINT config_index_pkey PRIMARY KEY (id);


--
-- Name: conversation_archives conversation_archives_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.conversation_archives
    ADD CONSTRAINT conversation_archives_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: debug_logs debug_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.debug_logs
    ADD CONSTRAINT debug_logs_pkey PRIMARY KEY (id);


--
-- Name: error_codes error_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.error_codes
    ADD CONSTRAINT error_codes_pkey PRIMARY KEY (code);


--
-- Name: error_history error_history_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.error_history
    ADD CONSTRAINT error_history_pkey PRIMARY KEY (hash);


--
-- Name: error_patterns error_patterns_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.error_patterns
    ADD CONSTRAINT error_patterns_pkey PRIMARY KEY (hash);


--
-- Name: event_items event_items_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.event_items
    ADD CONSTRAINT event_items_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: file_index file_index_file_path_zone_sub_zone_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.file_index
    ADD CONSTRAINT file_index_file_path_zone_sub_zone_key UNIQUE (file_path, zone, sub_zone);


--
-- Name: file_index file_index_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.file_index
    ADD CONSTRAINT file_index_pkey PRIMARY KEY (id);


--
-- Name: file_versions file_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.file_versions
    ADD CONSTRAINT file_versions_pkey PRIMARY KEY (id);


--
-- Name: ha_automations ha_automations_entity_id_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_automations
    ADD CONSTRAINT ha_automations_entity_id_key UNIQUE (entity_id);


--
-- Name: ha_automations ha_automations_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_automations
    ADD CONSTRAINT ha_automations_pkey PRIMARY KEY (id);


--
-- Name: ha_devices ha_devices_entity_id_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_devices
    ADD CONSTRAINT ha_devices_entity_id_key UNIQUE (entity_id);


--
-- Name: ha_devices ha_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_devices
    ADD CONSTRAINT ha_devices_pkey PRIMARY KEY (id);


--
-- Name: ha_entities ha_entities_entity_id_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_entities
    ADD CONSTRAINT ha_entities_entity_id_key UNIQUE (entity_id);


--
-- Name: ha_entities ha_entities_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_entities
    ADD CONSTRAINT ha_entities_pkey PRIMARY KEY (id);


--
-- Name: ha_integrations ha_integrations_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_integrations
    ADD CONSTRAINT ha_integrations_name_key UNIQUE (name);


--
-- Name: ha_integrations ha_integrations_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_integrations
    ADD CONSTRAINT ha_integrations_pkey PRIMARY KEY (id);


--
-- Name: ha_scenes ha_scenes_entity_id_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_scenes
    ADD CONSTRAINT ha_scenes_entity_id_key UNIQUE (entity_id);


--
-- Name: ha_scenes ha_scenes_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.ha_scenes
    ADD CONSTRAINT ha_scenes_pkey PRIMARY KEY (id);


--
-- Name: heartbeat_checks heartbeat_checks_component_check_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.heartbeat_checks
    ADD CONSTRAINT heartbeat_checks_component_check_name_key UNIQUE (component, check_name);


--
-- Name: heartbeat_checks heartbeat_checks_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.heartbeat_checks
    ADD CONSTRAINT heartbeat_checks_pkey PRIMARY KEY (id);


--
-- Name: heartbeat_log heartbeat_log_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.heartbeat_log
    ADD CONSTRAINT heartbeat_log_pkey PRIMARY KEY (id);


--
-- Name: indexed_files indexed_files_file_path_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.indexed_files
    ADD CONSTRAINT indexed_files_file_path_key UNIQUE (file_path);


--
-- Name: indexed_files indexed_files_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.indexed_files
    ADD CONSTRAINT indexed_files_pkey PRIMARY KEY (id);


--
-- Name: iso_builds iso_builds_build_id_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_builds
    ADD CONSTRAINT iso_builds_build_id_key UNIQUE (build_id);


--
-- Name: iso_builds iso_builds_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_builds
    ADD CONSTRAINT iso_builds_pkey PRIMARY KEY (id);


--
-- Name: iso_test_results iso_test_results_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_test_results
    ADD CONSTRAINT iso_test_results_pkey PRIMARY KEY (id);


--
-- Name: iso_types iso_types_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_types
    ADD CONSTRAINT iso_types_name_key UNIQUE (name);


--
-- Name: iso_types iso_types_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_types
    ADD CONSTRAINT iso_types_pkey PRIMARY KEY (id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);


--
-- Name: knowledge_base knowledge_base_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.knowledge_base
    ADD CONSTRAINT knowledge_base_pkey PRIMARY KEY (id);


--
-- Name: lab_changelog lab_changelog_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_changelog
    ADD CONSTRAINT lab_changelog_pkey PRIMARY KEY (id);


--
-- Name: lab_decisions lab_decisions_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_decisions
    ADD CONSTRAINT lab_decisions_pkey PRIMARY KEY (id);


--
-- Name: lab_discussions lab_discussions_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_discussions
    ADD CONSTRAINT lab_discussions_pkey PRIMARY KEY (id);


--
-- Name: lab_experiments lab_experiments_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_experiments
    ADD CONSTRAINT lab_experiments_pkey PRIMARY KEY (id);


--
-- Name: lab_fragments lab_fragments_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_fragments
    ADD CONSTRAINT lab_fragments_pkey PRIMARY KEY (id);


--
-- Name: lab_ideas lab_ideas_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_ideas
    ADD CONSTRAINT lab_ideas_pkey PRIMARY KEY (id);


--
-- Name: lab_implementations lab_implementations_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_implementations
    ADD CONSTRAINT lab_implementations_pkey PRIMARY KEY (id);


--
-- Name: log_entries log_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.log_entries
    ADD CONSTRAINT log_entries_pkey PRIMARY KEY (id);


--
-- Name: memories memories_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.memories
    ADD CONSTRAINT memories_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: module_preferences module_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.module_preferences
    ADD CONSTRAINT module_preferences_pkey PRIMARY KEY (id);


--
-- Name: nanite_commands nanite_commands_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.nanite_commands
    ADD CONSTRAINT nanite_commands_pkey PRIMARY KEY (id);


--
-- Name: nanite_nodes nanite_nodes_node_id_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.nanite_nodes
    ADD CONSTRAINT nanite_nodes_node_id_key UNIQUE (node_id);


--
-- Name: nanite_nodes nanite_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.nanite_nodes
    ADD CONSTRAINT nanite_nodes_pkey PRIMARY KEY (id);


--
-- Name: notes notes_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_pkey PRIMARY KEY (id);


--
-- Name: place_relations place_relations_from_place_id_to_place_id_relation_type_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.place_relations
    ADD CONSTRAINT place_relations_from_place_id_to_place_id_relation_type_key UNIQUE (from_place_id, to_place_id, relation_type);


--
-- Name: place_relations place_relations_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.place_relations
    ADD CONSTRAINT place_relations_pkey PRIMARY KEY (id);


--
-- Name: places places_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.places
    ADD CONSTRAINT places_pkey PRIMARY KEY (id);


--
-- Name: playbooks playbooks_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.playbooks
    ADD CONSTRAINT playbooks_name_key UNIQUE (name);


--
-- Name: playbooks playbooks_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.playbooks
    ADD CONSTRAINT playbooks_pkey PRIMARY KEY (id);


--
-- Name: procedures procedures_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.procedures
    ADD CONSTRAINT procedures_name_key UNIQUE (name);


--
-- Name: procedures procedures_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.procedures
    ADD CONSTRAINT procedures_pkey PRIMARY KEY (id);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: prompt_modules prompt_modules_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.prompt_modules
    ADD CONSTRAINT prompt_modules_name_key UNIQUE (name);


--
-- Name: prompt_modules prompt_modules_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.prompt_modules
    ADD CONSTRAINT prompt_modules_pkey PRIMARY KEY (id);


--
-- Name: proxmox_servers proxmox_servers_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.proxmox_servers
    ADD CONSTRAINT proxmox_servers_name_key UNIQUE (name);


--
-- Name: proxmox_servers proxmox_servers_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.proxmox_servers
    ADD CONSTRAINT proxmox_servers_pkey PRIMARY KEY (id);


--
-- Name: reasoning_axioms reasoning_axioms_domain_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.reasoning_axioms
    ADD CONSTRAINT reasoning_axioms_domain_key UNIQUE (domain);


--
-- Name: reasoning_axioms reasoning_axioms_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.reasoning_axioms
    ADD CONSTRAINT reasoning_axioms_pkey PRIMARY KEY (id);


--
-- Name: reasoning_log reasoning_log_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.reasoning_log
    ADD CONSTRAINT reasoning_log_pkey PRIMARY KEY (id);


--
-- Name: segments segments_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.segments
    ADD CONSTRAINT segments_pkey PRIMARY KEY (id);


--
-- Name: settings settings_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pkey PRIMARY KEY (key);


--
-- Name: skills skills_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.skills
    ADD CONSTRAINT skills_name_key UNIQUE (name);


--
-- Name: skills skills_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.skills
    ADD CONSTRAINT skills_pkey PRIMARY KEY (id);


--
-- Name: skills_tree skills_tree_path_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.skills_tree
    ADD CONSTRAINT skills_tree_path_key UNIQUE (path);


--
-- Name: skills_tree skills_tree_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.skills_tree
    ADD CONSTRAINT skills_tree_pkey PRIMARY KEY (id);


--
-- Name: system_credentials system_credentials_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.system_credentials
    ADD CONSTRAINT system_credentials_pkey PRIMARY KEY (id);


--
-- Name: system_modules system_modules_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.system_modules
    ADD CONSTRAINT system_modules_name_key UNIQUE (name);


--
-- Name: system_modules system_modules_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.system_modules
    ADD CONSTRAINT system_modules_pkey PRIMARY KEY (id);


--
-- Name: system_profiles system_profiles_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.system_profiles
    ADD CONSTRAINT system_profiles_name_key UNIQUE (name);


--
-- Name: system_profiles system_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.system_profiles
    ADD CONSTRAINT system_profiles_pkey PRIMARY KEY (id);


--
-- Name: targets targets_name_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.targets
    ADD CONSTRAINT targets_name_key UNIQUE (name);


--
-- Name: targets targets_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.targets
    ADD CONSTRAINT targets_pkey PRIMARY KEY (id);


--
-- Name: tool_scores tool_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.tool_scores
    ADD CONSTRAINT tool_scores_pkey PRIMARY KEY (id);


--
-- Name: tool_scores tool_scores_tool_name_task_type_key; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.tool_scores
    ADD CONSTRAINT tool_scores_tool_name_task_type_key UNIQUE (tool_name, task_type);


--
-- Name: working_memory wm_conv_active_unique; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.working_memory
    ADD CONSTRAINT wm_conv_active_unique UNIQUE (conversation_id, status);


--
-- Name: working_memory wm_conv_unique; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.working_memory
    ADD CONSTRAINT wm_conv_unique UNIQUE (conversation_id);


--
-- Name: working_memory working_memory_pkey; Type: CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.working_memory
    ADD CONSTRAINT working_memory_pkey PRIMARY KEY (id);


--
-- Name: idx_cristin_dh_mac; Type: INDEX; Schema: cristin; Owner: claude
--

CREATE INDEX idx_cristin_dh_mac ON cristin.device_history USING btree (mac);


--
-- Name: idx_cristin_dh_time; Type: INDEX; Schema: cristin; Owner: claude
--

CREATE INDEX idx_cristin_dh_time ON cristin.device_history USING btree (recorded_at DESC);


--
-- Name: idx_cristin_events_mac; Type: INDEX; Schema: cristin; Owner: claude
--

CREATE INDEX idx_cristin_events_mac ON cristin.events USING btree (mac);


--
-- Name: idx_cristin_events_severity; Type: INDEX; Schema: cristin; Owner: claude
--

CREATE INDEX idx_cristin_events_severity ON cristin.events USING btree (severity);


--
-- Name: idx_cristin_events_time; Type: INDEX; Schema: cristin; Owner: claude
--

CREATE INDEX idx_cristin_events_time ON cristin.events USING btree (recorded_at DESC);


--
-- Name: idx_disc_idea; Type: INDEX; Schema: lab; Owner: claude
--

CREATE INDEX idx_disc_idea ON lab.discussions USING btree (idea_id);


--
-- Name: idx_ideas_category; Type: INDEX; Schema: lab; Owner: claude
--

CREATE INDEX idx_ideas_category ON lab.ideas USING btree (category);


--
-- Name: idx_ideas_priority; Type: INDEX; Schema: lab; Owner: claude
--

CREATE INDEX idx_ideas_priority ON lab.ideas USING btree (priority);


--
-- Name: idx_ideas_status; Type: INDEX; Schema: lab; Owner: claude
--

CREATE INDEX idx_ideas_status ON lab.ideas USING btree (status);


--
-- Name: idx_impl_idea; Type: INDEX; Schema: lab; Owner: claude
--

CREATE INDEX idx_impl_idea ON lab.implementations USING btree (idea_id);


--
-- Name: idx_impl_status; Type: INDEX; Schema: lab; Owner: claude
--

CREATE INDEX idx_impl_status ON lab.implementations USING btree (status);


--
-- Name: idx_agent_sessions_active_phase; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_agent_sessions_active_phase ON public.agent_sessions USING btree (active, phase) WHERE (active = true);


--
-- Name: idx_agent_sessions_evidence_gin; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_agent_sessions_evidence_gin ON public.agent_sessions USING gin (evidence jsonb_path_ops);


--
-- Name: idx_agent_sessions_last_active; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_agent_sessions_last_active ON public.agent_sessions USING btree (last_active_at DESC);


--
-- Name: idx_agent_sessions_parent; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_agent_sessions_parent ON public.agent_sessions USING btree (parent_session_id) WHERE (parent_session_id IS NOT NULL);


--
-- Name: idx_agent_verif_rules_active_prio; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_agent_verif_rules_active_prio ON public.agent_verification_rules USING btree (active, priority) WHERE (active = true);


--
-- Name: idx_agent_verif_rules_type; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_agent_verif_rules_type ON public.agent_verification_rules USING btree (rule_type);


--
-- Name: idx_archives_conv; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_archives_conv ON public.conversation_archives USING btree (conversation_id);


--
-- Name: idx_archives_tags; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_archives_tags ON public.conversation_archives USING gin (tags);


--
-- Name: idx_auth_job; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_auth_job ON public.authorizations USING btree (job_id);


--
-- Name: idx_auth_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_auth_status ON public.authorizations USING btree (status);


--
-- Name: idx_debug_code; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_debug_code ON public.debug_logs USING btree (code);


--
-- Name: idx_debug_ts; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_debug_ts ON public.debug_logs USING btree (ts DESC);


--
-- Name: idx_ep_category; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_ep_category ON public.error_patterns USING btree (category);


--
-- Name: idx_ep_last_seen; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_ep_last_seen ON public.error_patterns USING btree (last_seen);


--
-- Name: idx_ep_resolved; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_ep_resolved ON public.error_patterns USING btree (resolved);


--
-- Name: idx_error_codes_file; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_error_codes_file ON public.error_codes USING btree (file_path);


--
-- Name: idx_error_codes_zone; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_error_codes_zone ON public.error_codes USING btree (zone);


--
-- Name: idx_event_items_done; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_event_items_done ON public.event_items USING btree (done);


--
-- Name: idx_event_items_event; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_event_items_event ON public.event_items USING btree (event_id);


--
-- Name: idx_events_place; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_events_place ON public.events USING btree (place_id);


--
-- Name: idx_events_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_events_status ON public.events USING btree (status);


--
-- Name: idx_events_target; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_events_target ON public.events USING btree (target_id);


--
-- Name: idx_events_when_date; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_events_when_date ON public.events USING btree (when_date);


--
-- Name: idx_file_index_autonomy; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_file_index_autonomy ON public.file_index USING btree (autonomy_level);


--
-- Name: idx_file_index_critical; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_file_index_critical ON public.file_index USING btree (critical);


--
-- Name: idx_file_index_managed; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_file_index_managed ON public.file_index USING btree (managed_by);


--
-- Name: idx_file_index_path; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_file_index_path ON public.file_index USING btree (file_path);


--
-- Name: idx_file_index_path_zone; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_file_index_path_zone ON public.file_index USING btree (file_path, zone);


--
-- Name: idx_file_index_zone; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_file_index_zone ON public.file_index USING btree (zone);


--
-- Name: idx_fv_module; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_fv_module ON public.file_versions USING btree (module_name, version_type);


--
-- Name: idx_hb_checks_component; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_hb_checks_component ON public.heartbeat_checks USING btree (component);


--
-- Name: idx_hb_checks_enabled; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_hb_checks_enabled ON public.heartbeat_checks USING btree (enabled);


--
-- Name: idx_hb_checks_group; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_hb_checks_group ON public.heartbeat_checks USING btree (display_group, display_order);


--
-- Name: idx_hb_checks_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_hb_checks_status ON public.heartbeat_checks USING btree (last_status);


--
-- Name: idx_hb_node_ts; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_hb_node_ts ON public.heartbeat_log USING btree (node, ts DESC);


--
-- Name: idx_iso_builds_build_id; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_iso_builds_build_id ON public.iso_builds USING btree (build_id);


--
-- Name: idx_iso_builds_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_iso_builds_status ON public.iso_builds USING btree (status);


--
-- Name: idx_iso_builds_type; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_iso_builds_type ON public.iso_builds USING btree (iso_type_id);


--
-- Name: idx_jobs_conversation; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_jobs_conversation ON public.jobs USING btree (conversation_id);


--
-- Name: idx_jobs_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_jobs_status ON public.jobs USING btree (status);


--
-- Name: idx_kb_category; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_kb_category ON public.knowledge_base USING btree (category);


--
-- Name: idx_kb_cmd_type; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_kb_cmd_type ON public.knowledge_base USING btree (command_type);


--
-- Name: idx_kb_os; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_kb_os ON public.knowledge_base USING btree (os_type, os_version);


--
-- Name: idx_kb_skip; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_kb_skip ON public.knowledge_base USING btree (skip) WHERE (skip = true);


--
-- Name: idx_kb_unique; Type: INDEX; Schema: public; Owner: claude
--

CREATE UNIQUE INDEX idx_kb_unique ON public.knowledge_base USING btree (os_type, os_version, command_type, action);


--
-- Name: idx_lab_changelog_date; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_lab_changelog_date ON public.lab_changelog USING btree (created_at DESC);


--
-- Name: idx_lab_disc_idea; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_lab_disc_idea ON public.lab_discussions USING btree (idea_id);


--
-- Name: idx_lab_exp_verdict; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_lab_exp_verdict ON public.lab_experiments USING btree (verdict);


--
-- Name: idx_lab_frag_tags; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_lab_frag_tags ON public.lab_fragments USING gin (tags);


--
-- Name: idx_lab_ideas_priority; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_lab_ideas_priority ON public.lab_ideas USING btree (priority);


--
-- Name: idx_lab_ideas_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_lab_ideas_status ON public.lab_ideas USING btree (status);


--
-- Name: idx_lab_ideas_tags; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_lab_ideas_tags ON public.lab_ideas USING gin (tags);


--
-- Name: idx_lab_impl_idea; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_lab_impl_idea ON public.lab_implementations USING btree (idea_id);


--
-- Name: idx_lab_impl_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_lab_impl_status ON public.lab_implementations USING btree (status);


--
-- Name: idx_log_entries_created; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_log_entries_created ON public.log_entries USING btree (created_at DESC);


--
-- Name: idx_log_entries_id; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_log_entries_id ON public.log_entries USING btree (id DESC);


--
-- Name: idx_messages_conv_created; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_messages_conv_created ON public.messages USING btree (conversation_id, created_at DESC);


--
-- Name: idx_nanite_cmd_node; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_nanite_cmd_node ON public.nanite_commands USING btree (node_id, status);


--
-- Name: idx_nanite_ip; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_nanite_ip ON public.nanite_nodes USING btree (ip);


--
-- Name: idx_nanite_last_seen; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_nanite_last_seen ON public.nanite_nodes USING btree (last_seen DESC);


--
-- Name: idx_nanite_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_nanite_status ON public.nanite_nodes USING btree (status);


--
-- Name: idx_notes_category; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_notes_category ON public.notes USING btree (category);


--
-- Name: idx_notes_event; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_notes_event ON public.notes USING btree (event_id);


--
-- Name: idx_notes_place; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_notes_place ON public.notes USING btree (place_id);


--
-- Name: idx_notes_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_notes_status ON public.notes USING btree (status);


--
-- Name: idx_notes_target; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_notes_target ON public.notes USING btree (target_id);


--
-- Name: idx_place_rel_from; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_place_rel_from ON public.place_relations USING btree (from_place_id);


--
-- Name: idx_place_rel_to; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_place_rel_to ON public.place_relations USING btree (to_place_id);


--
-- Name: idx_places_city; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_places_city ON public.places USING btree (city);


--
-- Name: idx_places_confirmed; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_places_confirmed ON public.places USING btree (confirmed);


--
-- Name: idx_places_name; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_places_name ON public.places USING gin (to_tsvector('simple'::regconfig, name));


--
-- Name: idx_pm_keywords; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_pm_keywords ON public.prompt_modules USING gin (keywords);


--
-- Name: idx_rl_conv; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_rl_conv ON public.reasoning_log USING btree (conversation_id, ts DESC);


--
-- Name: idx_sc_system; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_sc_system ON public.system_credentials USING btree (system_id);


--
-- Name: idx_scratchpad_conv; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_scratchpad_conv ON public.chat_scratchpad USING btree (conversation_id) WHERE (conversation_id IS NOT NULL);


--
-- Name: idx_scratchpad_expires; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_scratchpad_expires ON public.chat_scratchpad USING btree (expires_at) WHERE (expires_at IS NOT NULL);


--
-- Name: idx_scratchpad_recent; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_scratchpad_recent ON public.chat_scratchpad USING btree (last_seen_at DESC);


--
-- Name: idx_scratchpad_session; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_scratchpad_session ON public.chat_scratchpad USING btree (session_key) WHERE (session_key IS NOT NULL);


--
-- Name: idx_skills_tree_parent; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_skills_tree_parent ON public.skills_tree USING btree (parent_path);


--
-- Name: idx_skills_tree_path; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_skills_tree_path ON public.skills_tree USING btree (path);


--
-- Name: idx_skills_tree_tags; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_skills_tree_tags ON public.skills_tree USING gin (tags);


--
-- Name: idx_sp_name; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_sp_name ON public.system_profiles USING btree (name);


--
-- Name: idx_test_results_build; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_test_results_build ON public.iso_test_results USING btree (build_id);


--
-- Name: idx_wm_conv; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_wm_conv ON public.working_memory USING btree (conversation_id);


--
-- Name: idx_wm_status; Type: INDEX; Schema: public; Owner: claude
--

CREATE INDEX idx_wm_status ON public.working_memory USING btree (status);


--
-- Name: memories_key_unique; Type: INDEX; Schema: public; Owner: claude
--

CREATE UNIQUE INDEX memories_key_unique ON public.memories USING btree (key) WHERE (project_id IS NULL);


--
-- Name: uq_agent_verif_rules_pattern_type_active; Type: INDEX; Schema: public; Owner: claude
--

CREATE UNIQUE INDEX uq_agent_verif_rules_pattern_type_active ON public.agent_verification_rules USING btree (pattern, rule_type) WHERE (active = true);


--
-- Name: uq_scratchpad_conv_key; Type: INDEX; Schema: public; Owner: claude
--

CREATE UNIQUE INDEX uq_scratchpad_conv_key ON public.chat_scratchpad USING btree (conversation_id, note_key) WHERE (conversation_id IS NOT NULL);


--
-- Name: uq_scratchpad_session_key; Type: INDEX; Schema: public; Owner: claude
--

CREATE UNIQUE INDEX uq_scratchpad_session_key ON public.chat_scratchpad USING btree (session_key, note_key) WHERE (session_key IS NOT NULL);


--
-- Name: ideas trg_ideas_updated; Type: TRIGGER; Schema: lab; Owner: claude
--

CREATE TRIGGER trg_ideas_updated BEFORE UPDATE ON lab.ideas FOR EACH ROW EXECUTE FUNCTION lab.set_updated_at();


--
-- Name: implementations trg_impl_updated; Type: TRIGGER; Schema: lab; Owner: claude
--

CREATE TRIGGER trg_impl_updated BEFORE UPDATE ON lab.implementations FOR EACH ROW EXECUTE FUNCTION lab.set_updated_at();


--
-- Name: heartbeat_log heartbeat_cleanup; Type: TRIGGER; Schema: public; Owner: claude
--

CREATE TRIGGER heartbeat_cleanup AFTER INSERT ON public.heartbeat_log FOR EACH ROW EXECUTE FUNCTION public.cleanup_heartbeat();


--
-- Name: skills_tree skills_tree_touch_updated_at; Type: TRIGGER; Schema: public; Owner: claude
--

CREATE TRIGGER skills_tree_touch_updated_at BEFORE UPDATE ON public.skills_tree FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();


--
-- Name: agent_verification_rules trg_agent_verif_rules_touch; Type: TRIGGER; Schema: public; Owner: claude
--

CREATE TRIGGER trg_agent_verif_rules_touch BEFORE UPDATE ON public.agent_verification_rules FOR EACH ROW EXECUTE FUNCTION public.agent_verif_rules_touch();


--
-- Name: chat_scratchpad trg_chat_scratchpad_touch; Type: TRIGGER; Schema: public; Owner: claude
--

CREATE TRIGGER trg_chat_scratchpad_touch BEFORE UPDATE ON public.chat_scratchpad FOR EACH ROW EXECUTE FUNCTION public.chat_scratchpad_touch();


--
-- Name: decisions decisions_idea_id_fkey; Type: FK CONSTRAINT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.decisions
    ADD CONSTRAINT decisions_idea_id_fkey FOREIGN KEY (idea_id) REFERENCES lab.ideas(id);


--
-- Name: discussions discussions_idea_id_fkey; Type: FK CONSTRAINT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.discussions
    ADD CONSTRAINT discussions_idea_id_fkey FOREIGN KEY (idea_id) REFERENCES lab.ideas(id) ON DELETE CASCADE;


--
-- Name: discussions discussions_reply_to_fkey; Type: FK CONSTRAINT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.discussions
    ADD CONSTRAINT discussions_reply_to_fkey FOREIGN KEY (reply_to) REFERENCES lab.discussions(id);


--
-- Name: implementations implementations_idea_id_fkey; Type: FK CONSTRAINT; Schema: lab; Owner: claude
--

ALTER TABLE ONLY lab.implementations
    ADD CONSTRAINT implementations_idea_id_fkey FOREIGN KEY (idea_id) REFERENCES lab.ideas(id) ON DELETE CASCADE;


--
-- Name: agent_sessions agent_sessions_parent_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.agent_sessions
    ADD CONSTRAINT agent_sessions_parent_session_id_fkey FOREIGN KEY (parent_session_id) REFERENCES public.agent_sessions(id) ON DELETE SET NULL;


--
-- Name: artifacts artifacts_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.artifacts
    ADD CONSTRAINT artifacts_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: authorizations authorizations_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.authorizations
    ADD CONSTRAINT authorizations_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id);


--
-- Name: calup_commands calup_commands_calup_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.calup_commands
    ADD CONSTRAINT calup_commands_calup_id_fkey FOREIGN KEY (calup_id) REFERENCES public.calup_scores(id) ON DELETE CASCADE;


--
-- Name: calup_commands calup_commands_command_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.calup_commands
    ADD CONSTRAINT calup_commands_command_id_fkey FOREIGN KEY (command_id) REFERENCES public.command_scores(id) ON DELETE CASCADE;


--
-- Name: conversation_archives conversation_archives_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.conversation_archives
    ADD CONSTRAINT conversation_archives_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: conversations conversations_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: event_items event_items_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.event_items
    ADD CONSTRAINT event_items_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: events events_place_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_place_id_fkey FOREIGN KEY (place_id) REFERENCES public.places(id) ON DELETE SET NULL;


--
-- Name: events events_target_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_target_id_fkey FOREIGN KEY (target_id) REFERENCES public.targets(id) ON DELETE SET NULL;


--
-- Name: iso_builds iso_builds_iso_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_builds
    ADD CONSTRAINT iso_builds_iso_type_id_fkey FOREIGN KEY (iso_type_id) REFERENCES public.iso_types(id);


--
-- Name: iso_builds iso_builds_proxmox_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_builds
    ADD CONSTRAINT iso_builds_proxmox_server_id_fkey FOREIGN KEY (proxmox_server_id) REFERENCES public.proxmox_servers(id);


--
-- Name: iso_test_results iso_test_results_build_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_test_results
    ADD CONSTRAINT iso_test_results_build_id_fkey FOREIGN KEY (build_id) REFERENCES public.iso_builds(build_id);


--
-- Name: iso_test_results iso_test_results_proxmox_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.iso_test_results
    ADD CONSTRAINT iso_test_results_proxmox_server_id_fkey FOREIGN KEY (proxmox_server_id) REFERENCES public.proxmox_servers(id);


--
-- Name: jobs jobs_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id);


--
-- Name: knowledge_base knowledge_base_iso_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.knowledge_base
    ADD CONSTRAINT knowledge_base_iso_type_id_fkey FOREIGN KEY (iso_type_id) REFERENCES public.iso_types(id);


--
-- Name: lab_changelog lab_changelog_idea_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_changelog
    ADD CONSTRAINT lab_changelog_idea_id_fkey FOREIGN KEY (idea_id) REFERENCES public.lab_ideas(id);


--
-- Name: lab_changelog lab_changelog_impl_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_changelog
    ADD CONSTRAINT lab_changelog_impl_id_fkey FOREIGN KEY (impl_id) REFERENCES public.lab_implementations(id);


--
-- Name: lab_decisions lab_decisions_superseded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_decisions
    ADD CONSTRAINT lab_decisions_superseded_by_fkey FOREIGN KEY (superseded_by) REFERENCES public.lab_decisions(id);


--
-- Name: lab_discussions lab_discussions_idea_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_discussions
    ADD CONSTRAINT lab_discussions_idea_id_fkey FOREIGN KEY (idea_id) REFERENCES public.lab_ideas(id) ON DELETE CASCADE;


--
-- Name: lab_discussions lab_discussions_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_discussions
    ADD CONSTRAINT lab_discussions_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.lab_discussions(id);


--
-- Name: lab_experiments lab_experiments_idea_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_experiments
    ADD CONSTRAINT lab_experiments_idea_id_fkey FOREIGN KEY (idea_id) REFERENCES public.lab_ideas(id);


--
-- Name: lab_implementations lab_implementations_idea_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.lab_implementations
    ADD CONSTRAINT lab_implementations_idea_id_fkey FOREIGN KEY (idea_id) REFERENCES public.lab_ideas(id) ON DELETE CASCADE;


--
-- Name: memories memories_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.memories
    ADD CONSTRAINT memories_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id);


--
-- Name: nanite_nodes nanite_nodes_installed_system_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.nanite_nodes
    ADD CONSTRAINT nanite_nodes_installed_system_id_fkey FOREIGN KEY (installed_system_id) REFERENCES public.system_profiles(id);


--
-- Name: notes notes_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE SET NULL;


--
-- Name: notes notes_place_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_place_id_fkey FOREIGN KEY (place_id) REFERENCES public.places(id) ON DELETE SET NULL;


--
-- Name: notes notes_target_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_target_id_fkey FOREIGN KEY (target_id) REFERENCES public.targets(id) ON DELETE SET NULL;


--
-- Name: place_relations place_relations_from_place_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.place_relations
    ADD CONSTRAINT place_relations_from_place_id_fkey FOREIGN KEY (from_place_id) REFERENCES public.places(id) ON DELETE CASCADE;


--
-- Name: place_relations place_relations_to_place_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.place_relations
    ADD CONSTRAINT place_relations_to_place_id_fkey FOREIGN KEY (to_place_id) REFERENCES public.places(id) ON DELETE CASCADE;


--
-- Name: projects projects_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.projects(id);


--
-- Name: reasoning_log reasoning_log_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.reasoning_log
    ADD CONSTRAINT reasoning_log_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id);


--
-- Name: segments segments_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.segments
    ADD CONSTRAINT segments_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id);


--
-- Name: system_credentials system_credentials_system_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.system_credentials
    ADD CONSTRAINT system_credentials_system_id_fkey FOREIGN KEY (system_id) REFERENCES public.system_profiles(id);


--
-- Name: working_memory working_memory_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: claude
--

ALTER TABLE ONLY public.working_memory
    ADD CONSTRAINT working_memory_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id);


--
-- PostgreSQL database dump complete
--

\unrestrict boqcEib96QABcrQRdIGiPv7k2BhpmeSjwO1KWcCJ7jfwAqhVlPoEh4zJrGUVRGs

