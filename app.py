import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date, time
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
    """
    Combine a date and time into an ISO string with timezone.
    """
    dt_local = datetime.combine(selected_date, selected_time).replace(
        tzinfo=ZoneInfo(APP_TIMEZONE)
    )
    return dt_local.isoformat()


def format_ampm(dt_string: str) -> str:
    """
    Convert ISO datetime string into a friendly time like 3:15 PM.
    """
    dt = datetime.fromisoformat(dt_string)
    return dt.astimezone(ZoneInfo(APP_TIMEZONE)).strftime("%-I:%M %p")


def format_date_label(dt_string: str) -> str:
    """
    Used for entry list display.
    """
    dt = datetime.fromisoformat(dt_string).astimezone(ZoneInfo(APP_TIMEZONE))
    return dt.strftime("%-I:%M %p")


def format_relative_day(dt_string: str) -> str:
    """
    Returns '', 'today', or 'yesterday' style labels.
    """
    dt = datetime.fromisoformat(dt_string).astimezone(ZoneInfo(APP_TIMEZONE))
    today_local = get_now_local().date()

    if dt.date() == today_local:
        return "today"
    if dt.date() == (today_local.fromordinal(today_local.toordinal() - 1)):
        return "yesterday"
    return dt.strftime("on %b %-d")


def format_ounces(ounces_value) -> str:
    """
    Show 3 instead of 3.0, but keep 3.5 as 3.5.
    """
    ounces_float = float(ounces_value)
    if ounces_float.is_integer():
        return str(int(ounces_float))
    return str(ounces_float)


def ounces_options():
    """
    1.0 to 10.0 in 0.5 increments.
    """
    values = []
    current = 1.0
    while current <= 10.0:
        values.append(round(current, 1))
        current += 0.5
    return values


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


def get_today_feedings(baby_id: str):
    local_today = get_now_local().date()
    start_of_day = datetime.combine(local_today, time.min).replace(
        tzinfo=ZoneInfo(APP_TIMEZONE)
    )
    end_of_day = datetime.combine(local_today, time.max).replace(
        tzinfo=ZoneInfo(APP_TIMEZONE)
    )

    response = (
        supabase.table("feedings")
        .select("*")
        .eq("baby_id", baby_id)
        .gte("fed_at", start_of_day.isoformat())
        .lte("fed_at", end_of_day.isoformat())
        .order("fed_at", desc=True)
        .execute()
    )
    return response.data or []


def get_today_medications(baby_id: str):
    local_today = get_now_local().date()
    start_of_day = datetime.combine(local_today, time.min).replace(
        tzinfo=ZoneInfo(APP_TIMEZONE)
    )
    end_of_day = datetime.combine(local_today, time.max).replace(
        tzinfo=ZoneInfo(APP_TIMEZONE)
    )

    response = (
        supabase.table("medications")
        .select("*")
        .eq("baby_id", baby_id)
        .gte("given_at", start_of_day.isoformat())
        .lte("given_at", end_of_day.isoformat())
        .order("given_at", desc=True)
        .execute()
    )
    return response.data or []


def build_today_timeline(feedings, medications):
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
# TITLE
# -----------------------------
st.title("🍼 Baby Feeding Tracker")
st.caption("Track feedings and medications for today, while always showing the last feeding overall.")

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
        feeding_date = st.date_input("Feeding date", value=get_now_local().date(), key="feeding_date")
        feeding_time = st.time_input("Feeding time", value=get_now_local().time().replace(second=0, microsecond=0), key="feeding_time")
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
        medication_date = st.date_input("Medication date", value=get_now_local().date(), key="med_date")
        medication_time = st.time_input("Medication time", value=get_now_local().time().replace(second=0, microsecond=0), key="med_time")
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
# TODAY'S ENTRIES
# -----------------------------
st.divider()
st.subheader("Today’s Entries")

today_feedings = get_today_feedings(selected_baby_id)
today_medications = get_today_medications(selected_baby_id)
today_entries = build_today_timeline(today_feedings, today_medications)

if not today_entries:
    st.write("No entries for today yet.")
else:
    for entry in today_entries:
        display_time = format_date_label(entry["timestamp"])
        st.markdown(f"**{display_time}** — {entry['text']}")