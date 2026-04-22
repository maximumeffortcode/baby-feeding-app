import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Baby Feeding Tracker",
    page_icon="🍼",
    layout="centered",
)

# -----------------------------
# CONFIG
# -----------------------------
APP_TIMEZONE = "America/New_York"
FEEDING_DAY_START_HOUR = 4  # 4 AM -> 4 AM


# -----------------------------
# SUPABASE CONNECTION
# -----------------------------
@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = get_supabase_client()


# -----------------------------
# HELPERS
# -----------------------------
def get_now_local() -> datetime:
    return datetime.now(ZoneInfo(APP_TIMEZONE))


def combine_date_and_time(selected_date: date, selected_time: time) -> str:
    dt_local = datetime.combine(selected_date, selected_time).replace(
        tzinfo=ZoneInfo(APP_TIMEZONE)
    )
    return dt_local.isoformat()


def parse_iso_to_local(dt_string: str) -> datetime:
    return datetime.fromisoformat(dt_string).astimezone(ZoneInfo(APP_TIMEZONE))


def format_ampm(dt_string: str) -> str:
    dt = parse_iso_to_local(dt_string)
    return dt.strftime("%-I:%M %p")


def format_date_label(dt_string: str) -> str:
    dt = parse_iso_to_local(dt_string)
    return dt.strftime("%-I:%M %p")


def format_relative_day(dt_string: str) -> str:
    dt = parse_iso_to_local(dt_string)
    today_local = get_now_local().date()

    if dt.date() == today_local:
        return "today"
    if dt.date() == (today_local - timedelta(days=1)):
        return "yesterday"
    return dt.strftime("on %b %-d")


def format_time_since(dt_string: str) -> str:
    """
    Returns a friendly elapsed time like:
    45m ago
    2h 15m ago
    1d 3h ago
    """
    dt = parse_iso_to_local(dt_string)
    now_local = get_now_local()
    delta = now_local - dt

    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return "just now"

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    if days > 0:
        if hours > 0:
            return f"{days}d {hours}h ago"
        return f"{days}d ago"

    if hours > 0:
        if minutes > 0:
            return f"{hours}h {minutes}m ago"
        return f"{hours}h ago"

    return f"{minutes}m ago"


def format_ounces(ounces_value) -> str:
    ounces_float = float(ounces_value)
    if ounces_float.is_integer():
        return str(int(ounces_float))
    return str(ounces_float)


def ounces_options():
    values = []
    current = 1.0
    while current <= 10.0:
        values.append(round(current, 1))
        current += 0.5
    return values


def get_feeding_day_date(dt_local: datetime) -> date:
    adjusted = dt_local - timedelta(hours=FEEDING_DAY_START_HOUR)
    return adjusted.date()


def get_current_feeding_day_date() -> date:
    return get_feeding_day_date(get_now_local())


def get_feeding_day_bounds(target_feeding_day: date):
    tz = ZoneInfo(APP_TIMEZONE)
    start_dt = datetime.combine(
        target_feeding_day,
        time(FEEDING_DAY_START_HOUR, 0)
    ).replace(tzinfo=tz)
    end_dt = start_dt + timedelta(days=1)
    return start_dt, end_dt


def get_week_start(any_date: date) -> date:
    return any_date - timedelta(days=any_date.weekday())


def get_week_range_from_offset(week_offset: int):
    current_feeding_day = get_current_feeding_day_date()
    current_week_start = get_week_start(current_feeding_day)
    target_week_start = current_week_start + timedelta(weeks=week_offset)
    target_week_end = target_week_start + timedelta(days=6)
    return target_week_start, target_week_end


# -----------------------------
# SUPABASE QUERIES
# -----------------------------
def get_babies():
    response = (
        supabase.table("babies")
        .select("*")
        .order("name", desc=False)
        .execute()
    )
    return response.data or []


def get_last_feeding_overall(baby_id: str):
    response = (
        supabase.table("feedings")
        .select("*")
        .eq("baby_id", baby_id)
        .order("fed_at", desc=True)
        .limit(1)
        .execute()
    )
    data = response.data or []
    return data[0] if data else None


def get_last_medication_overall(baby_id: str):
    response = (
        supabase.table("medications")
        .select("*")
        .eq("baby_id", baby_id)
        .order("given_at", desc=True)
        .limit(1)
        .execute()
    )
    data = response.data or []
    return data[0] if data else None


def get_feedings_between(baby_id: str, start_iso: str, end_iso: str):
    response = (
        supabase.table("feedings")
        .select("*")
        .eq("baby_id", baby_id)
        .gte("fed_at", start_iso)
        .lt("fed_at", end_iso)
        .order("fed_at", desc=False)
        .execute()
    )
    return response.data or []


def get_medications_between(baby_id: str, start_iso: str, end_iso: str):
    response = (
        supabase.table("medications")
        .select("*")
        .eq("baby_id", baby_id)
        .gte("given_at", start_iso)
        .lt("given_at", end_iso)
        .order("given_at", desc=False)
        .execute()
    )
    return response.data or []


def get_current_feeding_day_feedings(baby_id: str):
    feeding_day = get_current_feeding_day_date()
    start_dt, end_dt = get_feeding_day_bounds(feeding_day)
    return get_feedings_between(baby_id, start_dt.isoformat(), end_dt.isoformat())


def get_current_feeding_day_medications(baby_id: str):
    feeding_day = get_current_feeding_day_date()
    start_dt, end_dt = get_feeding_day_bounds(feeding_day)
    return get_medications_between(baby_id, start_dt.isoformat(), end_dt.isoformat())


# -----------------------------
# APP LOGIC HELPERS
# -----------------------------
def build_feeding_day_timeline(feedings, medications):
    entries = []

    for feeding in feedings:
        entries.append(
            {
                "type": "feeding",
                "timestamp": feeding["fed_at"],
                "text": f'🍼 Fed {format_ounces(feeding["ounces"])} oz',
            }
        )

    for med in medications:
        entries.append(
            {
                "type": "medication",
                "timestamp": med["given_at"],
                "text": f'💊 {med["medication_name"]}',
            }
        )

    entries.sort(key=lambda x: x["timestamp"], reverse=True)
    return entries


def calculate_total_ounces_for_feeding_day(baby_id: str, feeding_day: date) -> float:
    start_dt, end_dt = get_feeding_day_bounds(feeding_day)
    feedings = get_feedings_between(baby_id, start_dt.isoformat(), end_dt.isoformat())
    return round(sum(float(f["ounces"]) for f in feedings), 1)


def get_daily_totals_for_week(baby_id: str, week_start: date, week_end: date):
    query_start_dt, _ = get_feeding_day_bounds(week_start)
    _, query_end_dt = get_feeding_day_bounds(week_end)

    feedings = get_feedings_between(
        baby_id,
        query_start_dt.isoformat(),
        query_end_dt.isoformat(),
    )

    totals_by_day = {}
    for i in range(7):
        day = week_start + timedelta(days=i)
        totals_by_day[day] = 0.0

    for feeding in feedings:
        dt_local = parse_iso_to_local(feeding["fed_at"])
        feeding_day = get_feeding_day_date(dt_local)
        if week_start <= feeding_day <= week_end:
            totals_by_day[feeding_day] += float(feeding["ounces"])

    rows = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        rows.append(
            {
                "date": day,
                "label": day.strftime("%a, %b %-d"),
                "total_ounces": round(totals_by_day[day], 1),
            }
        )

    return rows


def add_baby(name: str):
    supabase.table("babies").insert({"name": name}).execute()


def add_feeding(baby_id: str, ounces: float, fed_at_iso: str):
    supabase.table("feedings").insert(
        {
            "baby_id": baby_id,
            "ounces": ounces,
            "fed_at": fed_at_iso,
        }
    ).execute()


def add_medication(baby_id: str, medication_name: str, given_at_iso: str):
    supabase.table("medications").insert(
        {
            "baby_id": baby_id,
            "medication_name": medication_name,
            "given_at": given_at_iso,
        }
    ).execute()


# -----------------------------
# SESSION STATE
# -----------------------------
if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0


# -----------------------------
# TITLE
# -----------------------------
st.title("🍼 Baby Feeding Tracker")
st.caption(
    "Track feedings and medications, show the latest entry, and view daily ounce totals using a 4 AM to 4 AM feeding day."
)

# -----------------------------
# ADD BABY
# -----------------------------
with st.expander("Add Baby"):
    with st.form("add_baby_form", clear_on_submit=True):
        new_baby_name = st.text_input("Baby name")
        baby_submit = st.form_submit_button("Add Baby")

        if baby_submit:
            if not new_baby_name.strip():
                st.error("Please enter a baby name.")
            else:
                try:
                    add_baby(new_baby_name.strip())
                    st.success(f"{new_baby_name.strip()} added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add baby: {e}")

# -----------------------------
# BABY SELECTION
# -----------------------------
babies = get_babies()

if not babies:
    st.info("No babies added yet. Add a baby above to get started.")
    st.stop()

baby_options = {baby["name"]: baby["id"] for baby in babies}
selected_baby_name = st.selectbox("Select baby", options=list(baby_options.keys()))
selected_baby_id = baby_options[selected_baby_name]

# -----------------------------
# TOP SUMMARY
# -----------------------------
last_feeding = get_last_feeding_overall(selected_baby_id)
last_medication = get_last_medication_overall(selected_baby_id)
current_feeding_day = get_current_feeding_day_date()
current_feeding_day_total = calculate_total_ounces_for_feeding_day(
    selected_baby_id, current_feeding_day
)

st.subheader("Latest Summary")

if last_feeding:
    last_feed_day = format_relative_day(last_feeding["fed_at"])
    st.success(
        f'Last feeding: Baby {selected_baby_name} was fed '
        f'{format_ounces(last_feeding["ounces"])} ounces at '
        f'{format_ampm(last_feeding["fed_at"])} {last_feed_day}.'
    )
else:
    st.info("No feeding entries yet.")

if last_medication:
    last_med_day = format_relative_day(last_medication["given_at"])
    st.info(
        f'Last medication: {last_medication["medication_name"]} was given at '
        f'{format_ampm(last_medication["given_at"])} {last_med_day}.'
    )
else:
    st.caption("No medication entries yet.")

summary_col1, summary_col2 = st.columns(2)

with summary_col1:
    st.metric(
        label="Total ounces this feeding day",
        value=f"{format_ounces(current_feeding_day_total)} oz",
    )

with summary_col2:
    if last_feeding:
        st.metric(
            label="Time since last feeding",
            value=format_time_since(last_feeding["fed_at"]),
        )
    else:
        st.metric(
            label="Time since last feeding",
            value="—",
        )

st.caption("Feeding day runs from 4:00 AM to 4:00 AM.")

# -----------------------------
# ENTRY FORMS
# -----------------------------
st.divider()
col1, col2 = st.columns(2)

with col1:
    st.subheader("Add Feeding")
    last_ounces_default = 3.0
    if last_feeding:
        last_ounces_default = float(last_feeding["ounces"])

    ounce_list = ounces_options()
    default_index = ounce_list.index(last_ounces_default) if last_ounces_default in ounce_list else 4

    with st.form("feeding_form", clear_on_submit=True):
        feeding_date = st.date_input(
            "Feeding date",
            value=get_now_local().date(),
            key="feeding_date"
        )
        feeding_time = st.time_input(
            "Feeding time",
            value=get_now_local().time().replace(second=0, microsecond=0),
            key="feeding_time"
        )
        feeding_ounces = st.selectbox(
            "Ounces",
            options=ounce_list,
            index=default_index,
            format_func=lambda x: f"{format_ounces(x)} oz",
        )
        feeding_submit = st.form_submit_button("Save Feeding")

        if feeding_submit:
            try:
                fed_at_iso = combine_date_and_time(feeding_date, feeding_time)
                add_feeding(selected_baby_id, float(feeding_ounces), fed_at_iso)
                st.success("Feeding saved.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not save feeding: {e}")

with col2:
    st.subheader("Add Medication")
    medication_choices = ["Mylicon", "Gripe Water", "Vitamin D", "Other"]

    with st.form("medication_form", clear_on_submit=True):
        medication_date = st.date_input(
            "Medication date",
            value=get_now_local().date(),
            key="med_date"
        )
        medication_time = st.time_input(
            "Medication time",
            value=get_now_local().time().replace(second=0, microsecond=0),
            key="med_time"
        )
        medication_name = st.selectbox("Medication", options=medication_choices)

        custom_medication_name = ""
        if medication_name == "Other":
            custom_medication_name = st.text_input("Enter medication name")

        medication_submit = st.form_submit_button("Save Medication")

        if medication_submit:
            final_medication_name = medication_name
            if medication_name == "Other":
                final_medication_name = custom_medication_name.strip()

            if not final_medication_name:
                st.error("Please enter a medication name.")
            else:
                try:
                    given_at_iso = combine_date_and_time(medication_date, medication_time)
                    add_medication(selected_baby_id, final_medication_name, given_at_iso)
                    st.success("Medication saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not save medication: {e}")

# -----------------------------
# CURRENT FEEDING DAY ENTRIES
# -----------------------------
st.divider()
st.subheader("Today’s Entries (4 AM – 4 AM)")

feeding_day_feedings = get_current_feeding_day_feedings(selected_baby_id)
feeding_day_medications = get_current_feeding_day_medications(selected_baby_id)
feeding_day_entries = build_feeding_day_timeline(
    feeding_day_feedings,
    feeding_day_medications
)

if not feeding_day_entries:
    st.write("No entries for this feeding day yet.")
else:
    for entry in feeding_day_entries:
        display_time = format_date_label(entry["timestamp"])
        st.markdown(f"**{display_time}** — {entry['text']}")

# -----------------------------
# WEEKLY DAILY TOTALS
# -----------------------------
st.divider()
st.subheader("Daily Totals")

nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])

with nav_col1:
    if st.button("← Previous Week"):
        st.session_state.week_offset -= 1
        st.rerun()

with nav_col2:
    week_start, week_end = get_week_range_from_offset(st.session_state.week_offset)
    st.markdown(
        f"**Week of {week_start.strftime('%b %-d')} – {week_end.strftime('%b %-d')}**"
    )

with nav_col3:
    if st.session_state.week_offset < 0:
        if st.button("Next Week →"):
            st.session_state.week_offset += 1
            st.rerun()

weekly_totals = get_daily_totals_for_week(selected_baby_id, week_start, week_end)

for row in weekly_totals:
    total_display = f"{format_ounces(row['total_ounces'])} oz"
    if row["total_ounces"] == 0:
        total_display = "0 oz"
    st.markdown(f"**{row['label']}** — {total_display}")