import streamlit as st
import pymongo
from pymongo import MongoClient
from geopy.distance import geodesic
import pandas as pd
from datetime import datetime
import hashlib
import folium
from streamlit_folium import folium_static

# Page configuration
st.set_page_config(
    page_title="Smart Hospital Bed Allocation System",
    page_icon="🏥",
    layout="wide"
)

# MongoDB Connection
@st.cache_resource
def get_database_connection():
    try:
        client = MongoClient("mongodb+srv://ajaykarthik:1234@cluster0.wqelv.mongodb.net/?retryWrites=true&w=majority&EBT=Cluster0")
        db = client["Cluster0"]
        return db
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

db = get_database_connection()

# Hardcoded hospital data - only 3 hospitals
HOSPITALS = [
    {
        "hospital_name": "City Hospital",
        "username": "city_hospital_admin",
        "password": hashlib.sha256("adminpass".encode()).hexdigest(),
        "location": {"latitude": 12.9716, "longitude": 77.5946},
        "total_beds": 100,
        "available_beds": 25,
        "occupied_beds": 75,
        "patients": []
    },
    {
        "hospital_name": "General Hospital",
        "username": "general_hospital_admin",
        "password": hashlib.sha256("adminpass".encode()).hexdigest(),
        "location": {"latitude": 12.9200, "longitude": 77.6200},
        "total_beds": 150,
        "available_beds": 40,
        "occupied_beds": 110,
        "patients": []
    },
    {
        "hospital_name": "Medical Center",
        "username": "medical_center_admin",
        "password": hashlib.sha256("adminpass".encode()).hexdigest(),
        "location": {"latitude": 13.0200, "longitude": 77.5100},
        "total_beds": 80,
        "available_beds": 15,
        "occupied_beds": 65,
        "patients": []
    }
]

# Initialize collections if they don't exist
def initialize_collections():
    # Check if collections exist and create them if they don't
    if db is not None:
        # Create Users collection if it doesn't exist
        if "users" not in db.list_collection_names():
            users_collection = db["users"]
            users_collection.insert_one({"username": "patient1", "password": hashlib.sha256("password123".encode()).hexdigest()})
            st.sidebar.success("Users collection created!")
        
        # Create Hospitals collection if it doesn't exist
        if "hospitals" not in db.list_collection_names():
            hospitals_collection = db["hospitals"]
            hospitals_collection.insert_many(HOSPITALS)
            st.sidebar.success("Hospitals collection created!")
        
        # Create Bookings collection if it doesn't exist
        if "bookings" not in db.list_collection_names():
            bookings_collection = db["bookings"]
            st.sidebar.success("Bookings collection created!")

# Initialize collections
initialize_collections()

# Session state initialization
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_type' not in st.session_state:
    st.session_state.user_type = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'hospital_name' not in st.session_state:
    st.session_state.hospital_name = None
if 'patient_latitude' not in st.session_state:
    st.session_state.patient_latitude = None
if 'patient_longitude' not in st.session_state:
    st.session_state.patient_longitude = None

# Authentication Functions
def authenticate_user(username, password):
    if db is not None:
        users_collection = db["users"]
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        user = users_collection.find_one({"username": username, "password": hashed_password})
        if user:
            return True
    return False

def authenticate_hospital(username, password):
    if db is not None:
        hospitals_collection = db["hospitals"]
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        hospital = hospitals_collection.find_one({"username": username, "password": hashed_password})
        if hospital:
            st.session_state.hospital_name = hospital["hospital_name"]
            return True
    return False

# Logout Function
def logout():
    st.session_state.logged_in = False
    st.session_state.user_type = None
    st.session_state.username = None
    st.session_state.hospital_name = None
    st.session_state.patient_latitude = None
    st.session_state.patient_longitude = None

# Hospital Selection Logic
def find_nearest_hospital(patient_location, max_distance):
    hospitals_collection = db["hospitals"]
    hospitals = list(hospitals_collection.find({"available_beds": {"$gt": 0}}, 
                                             {"hospital_name": 1, "location": 1, "available_beds": 1}))
    
    hospital_distances = []
    for hospital in hospitals:
        hospital_location = (hospital["location"]["latitude"], hospital["location"]["longitude"])
        distance = geodesic(patient_location, hospital_location).km
        if distance <= max_distance:
            hospital_distances.append({
                "name": hospital["hospital_name"],
                "distance": distance,
                "available_beds": hospital["available_beds"]
            })
    
    if hospital_distances:
        # Sort by distance (primary) and available beds (secondary, in reverse)
        return sorted(hospital_distances, key=lambda x: (x["distance"], -x["available_beds"]))[0]
    return None

# Bed Booking Function
def book_hospital_bed(patient_name, phone, symptoms, hospital_name):
    try:
        # Update hospital bed count
        hospitals_collection = db["hospitals"]
        hospital = hospitals_collection.find_one({"hospital_name": hospital_name})
        
        if hospital and hospital["available_beds"] > 0:
            # Update hospital document
            hospitals_collection.update_one(
                {"hospital_name": hospital_name},
                {
                    "$inc": {"available_beds": -1, "occupied_beds": 1},
                    "$push": {
                        "patients": {
                            "name": patient_name,
                            "phone": phone,
                            "symptoms": symptoms,
                            "admission_date": datetime.now()
                        }
                    }
                }
            )
            
            # Create booking record
            bookings_collection = db["bookings"]
            bookings_collection.insert_one({
                "patient_name": patient_name,
                "phone": phone,
                "symptoms": symptoms,
                "hospital": hospital_name,
                "status": "Booked",
                "booking_date": datetime.now()
            })
            
            return True
        return False
    except Exception as e:
        st.error(f"Booking error: {e}")
        return False

# Main App UI
def main():
    st.title("🏥 Smart Hospital Bed Allocation System")
    
    # Sidebar for login/logout
    with st.sidebar:
        st.header("User Controls")
        
        if st.session_state.logged_in:
            st.success(f"Logged in as: {st.session_state.username} ({st.session_state.user_type})")
            if st.session_state.user_type == "hospital":
                st.info(f"Hospital: {st.session_state.hospital_name}")
            
            if st.button("Logout"):
                logout()
                st.rerun()  # Fixed: changed from experimental_rerun to rerun
        else:
            login_type = st.radio("Select Login Type:", ["Patient", "Hospital Admin"])
            
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            if st.button("Login"):
                if login_type == "Patient":
                    if authenticate_user(username, password):
                        st.session_state.logged_in = True
                        st.session_state.user_type = "patient"
                        st.session_state.username = username
                        st.rerun()  # Fixed: changed from experimental_rerun to rerun
                    else:
                        st.error("Invalid credentials!")
                else:  # Hospital Admin
                    if authenticate_hospital(username, password):
                        st.session_state.logged_in = True
                        st.session_state.user_type = "hospital"
                        st.session_state.username = username
                        st.rerun()  # Fixed: changed from experimental_rerun to rerun
                    else:
                        st.error("Invalid credentials!")
    
    # Main Content Area
    if not st.session_state.logged_in:
        # Landing page when not logged in
        st.info("Please login to access the system.")
        
        # Display system features
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Patient Features")
            st.markdown("""
            - Book hospital bed based on your location
            - Automatically find nearest hospital
            - Secure booking confirmation
            """)
        
        with col2:
            st.subheader("Hospital Admin Features")
            st.markdown("""
            - Manage bed availability
            - View admitted patients
            - Track hospital occupancy
            """)
    
    else:
        # User is logged in - show appropriate interface
        if st.session_state.user_type == "patient":
            display_patient_interface()
        else:  # hospital admin
            display_hospital_interface()

# Patient Interface
def display_patient_interface():
    st.header("📝 Book a Hospital Bed")
    
    # Patient Details Form
    with st.form("patient_details_form"):
        st.subheader("Patient Details")
        patient_name = st.text_input("Full Name", placeholder="Enter patient name")
        phone = st.text_input("Phone Number", placeholder="Enter contact number")
        symptoms = st.text_area("Symptoms", placeholder="Describe symptoms briefly")
        
        # Location capture
        st.subheader("📍 Patient Location")
        location_col1, location_col2 = st.columns(2)
        with location_col1:
            latitude = st.number_input("Latitude", value=12.97, format="%.4f")
        with location_col2:
            longitude = st.number_input("Longitude", value=77.59, format="%.4f")
        
        search_radius = st.slider("Maximum Search Distance (km)", min_value=5, max_value=30, value=10, step=5)
        
        find_hospital = st.form_submit_button("Find Nearest Hospital")
    
    # Process form submission
    if find_hospital:
        if not all([patient_name, phone, symptoms]):
            st.error("Please fill in all patient details!")
        else:
            st.session_state.patient_latitude = latitude
            st.session_state.patient_longitude = longitude
            
            # Find nearest hospital
            patient_location = (latitude, longitude)
            
            # Try to find hospital within increasing radius
            for radius in [10, 15, 20, search_radius]:
                nearest_hospital = find_nearest_hospital(patient_location, radius)
                if nearest_hospital:
                    break
            
            if nearest_hospital:
                st.success(f"Nearest hospital found: {nearest_hospital['name']} (Distance: {nearest_hospital['distance']:.2f} km)")
                
                # Display hospital details and booking option
                st.subheader("Hospital Details")
                st.markdown(f"""
                - **Hospital:** {nearest_hospital['name']}
                - **Distance:** {nearest_hospital['distance']:.2f} km
                - **Available Beds:** {nearest_hospital['available_beds']}
                """)
                
                # Show hospital on map
                hospital_info = db["hospitals"].find_one({"hospital_name": nearest_hospital['name']})
                if hospital_info:
                    m = folium.Map(location=[latitude, longitude], zoom_start=12)
                    
                    # Add patient marker
                    folium.Marker(
                        [latitude, longitude],
                        popup="Your Location",
                        icon=folium.Icon(color="blue", icon="user")
                    ).add_to(m)
                    
                    # Add hospital marker
                    hospital_lat = hospital_info["location"]["latitude"]
                    hospital_lon = hospital_info["location"]["longitude"]
                    folium.Marker(
                        [hospital_lat, hospital_lon],
                        popup=hospital_info["hospital_name"],
                        icon=folium.Icon(color="red", icon="plus")
                    ).add_to(m)
                    
                    # Add line between points
                    folium.PolyLine(
                        [(latitude, longitude), (hospital_lat, hospital_lon)],
                        color="green",
                        weight=2,
                        opacity=1
                    ).add_to(m)
                    
                    # Display map
                    st.subheader("📍 Location Map")
                    folium_static(m)
                
                # Confirm booking button
                if st.button("Book Now"):
                    if book_hospital_bed(patient_name, phone, symptoms, nearest_hospital['name']):
                        st.success("Hospital bed booked successfully!")
                        st.balloons()
                        
                        # Show booking details
                        st.subheader("Booking Details")
                        st.info(f"""
                        ✅ **Booking Confirmed!**
                        
                        Patient Name: {patient_name}
                        Hospital: {nearest_hospital['name']}
                        Distance: {nearest_hospital['distance']:.2f} km
                        Status: Booked
                        
                        Please proceed to the hospital with your ID proof.
                        """)
                    else:
                        st.error("Failed to book bed. Please try again!")
            else:
                st.error(f"No hospital with available beds found within {search_radius} km radius!")

# Hospital Admin Interface
def display_hospital_interface():
    st.header(f"🏥 {st.session_state.hospital_name} Dashboard")
    
    # Fetch current hospital data
    hospitals_collection = db["hospitals"]
    hospital_data = hospitals_collection.find_one({"hospital_name": st.session_state.hospital_name})
    
    if not hospital_data:
        st.error("Hospital data not found!")
        return
    
    # Dashboard metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Beds", hospital_data["total_beds"])
    with col2:
        st.metric("Available Beds", hospital_data["available_beds"])
    with col3:
        st.metric("Occupied Beds", hospital_data["occupied_beds"])
    with col4:
        occupancy_rate = (hospital_data["occupied_beds"] / hospital_data["total_beds"]) * 100
        st.metric("Occupancy Rate", f"{occupancy_rate:.1f}%")
    
    # Bed management section
    st.subheader("Bed Management")
    col1, col2 = st.columns(2)
    
    with col1:
        # Update bed availability
        with st.form("update_beds_form"):
            st.subheader("Update Bed Availability")
            new_total = st.number_input("Total Beds", min_value=0, value=hospital_data["total_beds"])
            new_available = st.number_input("Available Beds", min_value=0, max_value=new_total, value=hospital_data["available_beds"])
            
            if st.form_submit_button("Update Beds"):
                new_occupied = new_total - new_available
                hospitals_collection.update_one(
                    {"hospital_name": st.session_state.hospital_name},
                    {
                        "$set": {
                            "total_beds": new_total,
                            "available_beds": new_available,
                            "occupied_beds": new_occupied
                        }
                    }
                )
                st.success("Bed information updated successfully!")
                st.rerun()  # Fixed: changed from experimental_rerun to rerun
    
    with col2:
        # Hospital location info
        st.subheader("Hospital Location")
        hospital_lat = hospital_data["location"]["latitude"]
        hospital_lon = hospital_data["location"]["longitude"]
        
        m = folium.Map(location=[hospital_lat, hospital_lon], zoom_start=14)
        folium.Marker(
            [hospital_lat, hospital_lon],
            popup=hospital_data["hospital_name"],
            icon=folium.Icon(color="red", icon="plus", prefix="fa")
        ).add_to(m)
        folium_static(m)
    
    # Patients List
    st.subheader("Admitted Patients")
    if hospital_data["patients"]:
        patients_df = pd.DataFrame(hospital_data["patients"])
        if "admission_date" in patients_df.columns:
            patients_df["admission_date"] = pd.to_datetime(patients_df["admission_date"])
            patients_df["admission_date"] = patients_df["admission_date"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(patients_df, use_container_width=True)
    else:
        st.info("No patients currently admitted.")
    
    # Recent bookings
    st.subheader("Recent Bookings")
    bookings_collection = db["bookings"]
    recent_bookings = list(bookings_collection.find(
        {"hospital": st.session_state.hospital_name}
    ).sort("booking_date", pymongo.DESCENDING).limit(5))
    
    if recent_bookings:
        bookings_df = pd.DataFrame(recent_bookings)
        bookings_df["booking_date"] = pd.to_datetime(bookings_df["booking_date"])
        bookings_df["booking_date"] = bookings_df["booking_date"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(bookings_df[["patient_name", "phone", "symptoms", "booking_date", "status"]], use_container_width=True)
    else:
        st.info("No recent bookings found.")

if __name__ == "__main__":
    main()