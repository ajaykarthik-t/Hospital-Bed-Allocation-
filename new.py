import streamlit as st
import pymongo
from pymongo import MongoClient
from geopy.distance import geodesic
import pandas as pd
from datetime import datetime
import hashlib
import folium
from streamlit_folium import folium_static
from bson import ObjectId

# Page configuration
st.set_page_config(
    page_title="Smart Hospital Bed Allocation System",
    page_icon="🏥",
    layout="wide"
)

# MongoDB Connection - Updated with better error handling
@st.cache_resource(ttl=300)  # Cache for 5 minutes only to ensure fresh data
def get_database_connection():
    try:
        # More robust connection string - explicit database name
        client = MongoClient(
            "mongodb+srv://shreya:shreya@cluster0.2hywi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=5000,
            socketTimeoutMS=10000
        )
        
        # Test connection by attempting to get server info
        server_info = client.server_info()
        
        # Connect to the database explicitly
        db = client.Cluster0
        
        # Test database access by listing collections
        collection_names = db.list_collection_names()
        print(f"Connected to MongoDB. Available collections: {collection_names}")
        
        return db
    except Exception as e:
        st.error(f"Failed to connect to MongoDB: {str(e)}")
        print(f"MongoDB connection error details: {str(e)}")
        return None

# Get database connection
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
        try:
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
        except Exception as e:
            st.sidebar.error(f"Error initializing collections: {e}")

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
if 'booking_success' not in st.session_state:
    st.session_state.booking_success = False
if 'booking_error' not in st.session_state:
    st.session_state.booking_error = None
if 'booking_details' not in st.session_state:
    st.session_state.booking_details = None
if 'update_success' not in st.session_state:
    st.session_state.update_success = False
if 'update_error' not in st.session_state:
    st.session_state.update_error = None
if 'discharge_success' not in st.session_state:
    st.session_state.discharge_success = False
if 'discharge_error' not in st.session_state:
    st.session_state.discharge_error = None
if 'patient_info' not in st.session_state:
    st.session_state.patient_info = {}
if 'nearest_hospital' not in st.session_state:
    st.session_state.nearest_hospital = None

# Authentication Functions
def authenticate_user(username, password):
    if db is not None:
        try:
            users_collection = db["users"]
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            user = users_collection.find_one({"username": username, "password": hashed_password})
            if user:
                return True
        except Exception as e:
            st.error(f"Authentication error: {e}")
    return False

def authenticate_hospital(username, password):
    if db is not None:
        try:
            hospitals_collection = db["hospitals"]
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            hospital = hospitals_collection.find_one({"username": username, "password": hashed_password})
            if hospital:
                st.session_state.hospital_name = hospital["hospital_name"]
                return True
        except Exception as e:
            st.error(f"Hospital authentication error: {e}")
    return False

# Logout Function
def logout():
    st.session_state.logged_in = False
    st.session_state.user_type = None
    st.session_state.username = None
    st.session_state.hospital_name = None
    st.session_state.patient_latitude = None
    st.session_state.patient_longitude = None
    st.session_state.booking_success = False
    st.session_state.booking_error = None
    st.session_state.booking_details = None
    st.session_state.update_success = False
    st.session_state.update_error = None
    st.session_state.discharge_success = False
    st.session_state.discharge_error = None
    st.session_state.patient_info = {}
    st.session_state.nearest_hospital = None

# Hospital Selection Logic
def find_nearest_hospital(patient_location, max_distance):
    if db is None:
        st.error("Database connection not available")
        return None
    
    try:
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
    except Exception as e:
        st.error(f"Error finding nearest hospital: {e}")
        return None

# FIXED: Completely rewritten book_hospital_bed function
def book_hospital_bed(patient_name, phone, symptoms, hospital_name):
    if db is None:
        st.session_state.booking_error = "Database connection not available"
        print("Database connection not available")
        return False
    
    try:
        print(f"Starting booking process for {patient_name} at {hospital_name}")
        
        # Get hospitals collection
        hospitals_collection = db["hospitals"]
        bookings_collection = db["bookings"]
        
        # First, check if the hospital exists and has beds
        hospital = hospitals_collection.find_one({"hospital_name": hospital_name})
        
        if not hospital:
            st.session_state.booking_error = f"Hospital {hospital_name} not found"
            print(f"Hospital {hospital_name} not found")
            return False
            
        if hospital["available_beds"] <= 0:
            st.session_state.booking_error = f"No beds available in {hospital_name}"
            print(f"No beds available in {hospital_name}")
            return False
        
        # Check if patient is already admitted to this hospital
        patient_already_admitted = False
        if "patients" in hospital and hospital["patients"]:
            for patient in hospital["patients"]:
                if patient.get("name") == patient_name and patient.get("phone") == phone:
                    patient_already_admitted = True
                    break
                    
        if patient_already_admitted:
            st.session_state.booking_error = f"Patient {patient_name} already admitted to {hospital_name}"
            print(f"Patient {patient_name} already admitted to {hospital_name}")
            return False
        
        # Format the patient data
        patient_data = {
            "name": patient_name,
            "phone": phone,
            "symptoms": symptoms,
            "admission_date": datetime.now()
        }
        
        print(f"Patient data prepared: {patient_data}")
        
        # Create booking record first
        booking_data = {
            "patient_name": patient_name,
            "phone": phone,
            "symptoms": symptoms,
            "hospital": hospital_name,
            "status": "Booked",
            "booking_date": datetime.now()
        }
        
        print(f"Booking data prepared: {booking_data}")
        
        # Insert booking and save ID
        booking_result = bookings_collection.insert_one(booking_data)
        booking_id = booking_result.inserted_id
        
        if not booking_id:
            st.session_state.booking_error = "Failed to create booking record"
            print("Failed to create booking record")
            return False
            
        print(f"Booking created with ID: {booking_id}")
        
        # Update hospital with atomic operation
        result = hospitals_collection.update_one(
            {"hospital_name": hospital_name, "available_beds": {"$gt": 0}},
            {
                "$inc": {"available_beds": -1, "occupied_beds": 1},
                "$push": {"patients": patient_data}
            }
        )
        
        print(f"Hospital update result - matched: {result.matched_count}, modified: {result.modified_count}")
        
        # Check if update was successful
        if result.matched_count == 0:
            # Rollback - delete the booking we just created
            bookings_collection.delete_one({"_id": booking_id})
            st.session_state.booking_error = "No matching hospital with available beds found"
            print("No matching hospital with available beds found - rollback performed")
            return False
            
        if result.modified_count == 0:
            # Rollback - delete the booking we just created
            bookings_collection.delete_one({"_id": booking_id})
            st.session_state.booking_error = "Failed to update hospital data"
            print("Failed to update hospital data - rollback performed")
            return False
        
        print("Booking completed successfully")
        
        # Success - set session state for success message
        st.session_state.booking_success = True
        st.session_state.booking_details = {
            "patient_name": patient_name,
            "hospital": hospital_name,
            "booking_id": str(booking_id),
            "status": "Confirmed",
            "booking_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return True
            
    except Exception as e:
        error_msg = f"Error during booking: {str(e)}"
        print(f"Exception in booking: {error_msg}")
        st.session_state.booking_error = error_msg
        return False

# Patient Interface
def display_patient_interface():
    st.header("📝 Book a Hospital Bed")
    
    # Show booking result if available
    if st.session_state.booking_success:
        st.success("Hospital bed booked successfully! 🎉")
        st.balloons()
        
        # Display detailed booking information
        if st.session_state.booking_details:
            st.subheader("🎫 Booking Details")
            details = st.session_state.booking_details
            st.info(f"""
            ✅ **Booking Confirmed!**
            
            **Patient Name:** {details['patient_name']}
            **Hospital:** {details['hospital']}
            **Booking ID:** {details['booking_id']}
            **Status:** {details['status']}
            **Booking Time:** {details['booking_time']}
            
            Please proceed to the hospital with your ID proof and booking ID.
            """)
        
        # Add a button to make a new booking
        if st.button("Make a New Booking"):
            st.session_state.booking_success = False
            st.session_state.booking_details = None
            st.session_state.patient_info = {}
            st.session_state.nearest_hospital = None
            st.rerun()
        
        # Return early to avoid showing the booking form
        return
    
    if st.session_state.booking_error:
        st.error(f"⚠️ Booking failed: {st.session_state.booking_error}")
        # Don't reset the error here - we'll do it after displaying the form
    
    # Patient Details Form
    with st.form("patient_details_form"):
        st.subheader("Patient Details")
        
        # Pre-fill form fields if we have data in session state
        patient_name = st.text_input("Full Name", value=st.session_state.patient_info.get("name", ""), placeholder="Enter patient name")
        phone = st.text_input("Phone Number", value=st.session_state.patient_info.get("phone", ""), placeholder="Enter contact number")
        symptoms = st.text_area("Symptoms", value=st.session_state.patient_info.get("symptoms", ""), placeholder="Describe symptoms briefly")
        
        # Location capture
        st.subheader("📍 Patient Location")
        location_col1, location_col2 = st.columns(2)
        with location_col1:
            latitude = st.number_input("Latitude", value=st.session_state.patient_latitude or 12.97, format="%.4f")
        with location_col2:
            longitude = st.number_input("Longitude", value=st.session_state.patient_longitude or 77.59, format="%.4f")
        
        search_radius = st.slider("Maximum Search Distance (km)", min_value=5, max_value=30, value=10, step=5)
        
        find_hospital = st.form_submit_button("Find Nearest Hospital")
    
    # Reset error after displaying the form
    if st.session_state.booking_error:
        st.session_state.booking_error = None
    
    # Process form submission
    if find_hospital:
        if not all([patient_name, phone, symptoms]):
            st.error("Please fill in all patient details!")
        else:
            # Save patient info to session state
            st.session_state.patient_info = {
                "name": patient_name,
                "phone": phone, 
                "symptoms": symptoms
            }
            
            st.session_state.patient_latitude = latitude
            st.session_state.patient_longitude = longitude
            
            # Find nearest hospital
            patient_location = (latitude, longitude)
            
            # Try to find hospital within increasing radius
            nearest_hospital = None
            for radius in [search_radius, 15, 20, 30]:
                nearest_hospital = find_nearest_hospital(patient_location, radius)
                if nearest_hospital:
                    break
            
            # Save nearest hospital to session state
            st.session_state.nearest_hospital = nearest_hospital
            
            # Force refresh to show the hospital data
            st.rerun()
    
    # Display hospital information if we have it
    if st.session_state.nearest_hospital:
        nearest_hospital = st.session_state.nearest_hospital
        st.success(f"Nearest hospital found: {nearest_hospital['name']} (Distance: {nearest_hospital['distance']:.2f} km)")
        
        # Display hospital details and booking option
        st.subheader("Hospital Details")
        st.markdown(f"""
        - **Hospital:** {nearest_hospital['name']}
        - **Distance:** {nearest_hospital['distance']:.2f} km
        - **Available Beds:** {nearest_hospital['available_beds']}
        """)
        
        # Show hospital on map
        if db is not None:
            hospital_info = db["hospitals"].find_one({"hospital_name": nearest_hospital['name']})
            if hospital_info:
                m = folium.Map(location=[st.session_state.patient_latitude, st.session_state.patient_longitude], zoom_start=12)
                
                # Add patient marker
                folium.Marker(
                    [st.session_state.patient_latitude, st.session_state.patient_longitude],
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
                    [(st.session_state.patient_latitude, st.session_state.patient_longitude), 
                     (hospital_lat, hospital_lon)],
                    color="green",
                    weight=2,
                    opacity=1
                ).add_to(m)
                
                # Display map
                st.subheader("📍 Location Map")
                folium_static(m)
        
        # FIXED: Confirm booking button with progress indicator
        if st.button("Book Now"):
            with st.spinner("Processing your booking..."):
                patient_name = st.session_state.patient_info["name"]
                phone = st.session_state.patient_info["phone"]  
                symptoms = st.session_state.patient_info["symptoms"]
                
                print(f"Book Now button clicked - patient: {patient_name}, hospital: {nearest_hospital['name']}")
                
                # Call the booking function
                booking_success = book_hospital_bed(
                    patient_name=patient_name,
                    phone=phone,
                    symptoms=symptoms,
                    hospital_name=nearest_hospital['name']
                )
                
                print(f"Booking result: {booking_success}")
                
                if booking_success:
                    st.rerun()  # Refresh to show the success message
                else:
                    # Error will be shown at the top
                    st.rerun()

# Hospital Admin Interface
def display_hospital_interface():
    st.header(f"🏥 {st.session_state.hospital_name} Dashboard")
    
    # Check for notification states and display them
    if st.session_state.update_success:
        st.success("✅ Hospital bed count updated successfully!")
        st.session_state.update_success = False  # Reset after showing
    
    if st.session_state.update_error:
        st.error(f"⚠️ Update failed: {st.session_state.update_error}")
        st.session_state.update_error = None  # Reset after showing
        
    if st.session_state.discharge_success:
        st.success("✅ Patient discharged successfully!")
        st.session_state.discharge_success = False  # Reset after showing
        
    if st.session_state.discharge_error:
        st.error(f"⚠️ Discharge failed: {st.session_state.discharge_error}")
        st.session_state.discharge_error = None  # Reset after showing
    
    # Always fetch fresh data directly from MongoDB
    if db is None:
        st.error("Database connection not available. Unable to fetch hospital data.")
        return
    
    try:
        # Use a fresh query with no caching to get latest data
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
        
        # Add update available beds functionality
        st.subheader("Update Bed Count")
        with st.form("update_beds_form"):
            new_available = st.number_input("Update Available Beds", 
                                         min_value=0, 
                                         max_value=hospital_data["total_beds"],
                                         value=hospital_data["available_beds"])
            
            update_beds = st.form_submit_button("Update Bed Count")
            
        if update_beds:
            try:
                # Calculate new occupied count
                new_occupied = hospital_data["total_beds"] - new_available
                
                # Update in database
                update_result = hospitals_collection.update_one(
                    {"hospital_name": st.session_state.hospital_name},
                    {"$set": {"available_beds": new_available, "occupied_beds": new_occupied}}
                )
                
                if update_result.modified_count == 1:
                    st.session_state.update_success = True
                    st.rerun()
                else:
                    st.session_state.update_error = "No changes were made to bed count"
                    st.rerun()
            except Exception as e:
                st.session_state.update_error = f"Error updating bed count: {str(e)}"
                st.rerun()
        
        # Recent Bookings
        st.subheader("Recent Bookings")
        bookings_collection = db["bookings"]
        recent_bookings = list(bookings_collection.find(
            {"hospital": st.session_state.hospital_name}
        ).sort("booking_date", pymongo.DESCENDING).limit(5))
        
        if recent_bookings:
            for booking in recent_bookings:
                # Convert ObjectId to string and format date
                booking_id = str(booking["_id"])
                booking_date = booking["booking_date"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(booking["booking_date"], datetime) else booking["booking_date"]
                
                # Create an expandable section for each booking
                with st.expander(f"Booking: {booking['patient_name']} - {booking_date}"):
                    st.write(f"**Patient:** {booking['patient_name']}")
                    st.write(f"**Phone:** {booking['phone']}")
                    st.write(f"**Symptoms:** {booking['symptoms']}")
                    st.write(f"**Status:** {booking['status']}")
                    st.write(f"**Booking ID:** {booking_id}")
        else:
            st.info("No recent bookings found.")
        
        # Patients List
        st.subheader("Admitted Patients")
        if "patients" in hospital_data and hospital_data["patients"]:
            # Convert to list if it's not already
            patients_list = hospital_data["patients"] if isinstance(hospital_data["patients"], list) else []
            
            if patients_list:
                # Fix date format for display
                for patient in patients_list:
                    if "admission_date" in patient:
                        if isinstance(patient["admission_date"], datetime):
                            patient["admission_date"] = patient["admission_date"].strftime("%Y-%m-%d %H:%M:%S")
                
                patients_df = pd.DataFrame(patients_list)
                # Clean up display columns
                display_cols = [col for col in patients_df.columns if col != '_id']
                
                st.dataframe(patients_df[display_cols], use_container_width=True)
                
                # Add discharge patient functionality
                st.subheader("Discharge Patient")
                patient_names = ["Select a patient"] + list(patients_df["name"] if "name" in patients_df.columns else [])
                
                if len(patient_names) > 1:  # If we have patients
                    selected_patient = st.selectbox("Select Patient to Discharge", patient_names)
                    
                    if selected_patient != "Select a patient":
                        if st.button("Discharge Patient"):
                            try:
                                # Find the patient's phone
                                patient_info = patients_df[patients_df["name"] == selected_patient].iloc[0]
                                patient_phone = patient_info["phone"] if "phone" in patient_info else ""
                                
                                # Remove patient from hospital
                                result = hospitals_collection.update_one(
                                    {"hospital_name": st.session_state.hospital_name},
                                    {
                                        "$pull": {"patients": {"name": selected_patient, "phone": patient_phone}},
                                        "$inc": {"available_beds": 1, "occupied_beds": -1}
                                    }
                                )
                                
                                if result.modified_count == 1:
                                    st.session_state.discharge_success = True
                                    st.rerun()
                                else:
                                    st.session_state.discharge_error = "Failed to discharge patient"
                                    st.rerun()
                            except Exception as e:
                                st.session_state.discharge_error = f"Error discharging patient: {str(e)}"
                                st.rerun()
            else:
                st.info("No patients currently admitted.")
        else:
            st.info("No patients currently admitted.")
            
    except Exception as e:
        st.error(f"Error displaying hospital interface: {e}")

# Main App UI
def main():
    st.title("🏥 Smart Hospital Bed Allocation System")
    
    # Show MongoDB connection status
    if db is None:
        st.error("⚠️ Database connection failed. Some features may not work correctly.")
    
    # Sidebar for login/logout
    with st.sidebar:
        st.header("User Controls")
        
        if st.session_state.logged_in:
            st.success(f"Logged in as: {st.session_state.username} ({st.session_state.user_type})")
            if st.session_state.user_type == "hospital":
                st.info(f"Hospital: {st.session_state.hospital_name}")
            
            if st.button("Logout"):
                logout()
                st.rerun()
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
                        st.rerun()
                    else:
                        st.error("Invalid credentials!")
                else:  # Hospital Admin
                    if authenticate_hospital(username, password):
                        st.session_state.logged_in = True
                        st.session_state.user_type = "hospital"
                        st.session_state.username = username
                        st.rerun()
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

if __name__ == "__main__":
    main()  