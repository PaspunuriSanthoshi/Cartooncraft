import time
import cv2
import numpy as np
import streamlit as st
from io import BytesIO
from PIL import Image
from skimage.metrics import structural_similarity as ssim
import mysql.connector
import base64
import datetime

st.set_page_config(
    page_title="Cartoon Craft Web Application",
    page_icon="🌈",
    initial_sidebar_state="expanded",
    layout="wide",
)

# Establish MySQL connection
db_connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Santhoshi@2002",
    database="major"
)
cursor = db_connection.cursor()

# Create user table if not exists
cursor.execute("""
    CREATE TABLE IF NOT EXISTS db (
        username VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL UNIQUE,
        email VARCHAR(255) NOT NULL,
        dob DATE NOT NULL,
        occupation VARCHAR(255),
        profile_photo LONGBLOB,
        saved_images LONGTEXT
    )
""")
db_connection.commit()

fixed_image_url = Image.open(r"C:\Users\santh\OneDrive\Documents\Major Project\Home.jpeg")

# Session state to store user login status and username
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
if 'logged_in_username' not in st.session_state:
    st.session_state.logged_in_username = None

# Function to check login credentials
def authenticate(username, password):
    cursor.execute("SELECT * FROM db WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    return user is not None

# Function to register a new user with profile photo
def register(username, password, email, dob, occupation, profile_photo_data):
    try:
        if len(password) < 8:
            raise ValueError("Password should be at least 8 characters long")

        if not email.endswith('@gmail.com'):
            raise ValueError("Invalid email format. Please use a Gmail address")

        cursor.execute(
            "INSERT INTO db (username, password, email, dob, occupation, profile_photo) VALUES (%s, %s, %s, %s, %s, %s)",
            (username, password, email, dob, occupation, profile_photo_data))
        db_connection.commit()
        st.success("Registration successful! You can now log in.")
    except mysql.connector.Error as err:
        if err.errno == 1062:
            st.warning("Username already exists. Please choose a different username.")
        else:
            st.warning(f"An error occurred during registration: {err}")

# Function to save image for the current user
def save_image(username, image_data):
    try:
        cursor.execute(
            "SELECT saved_images FROM db WHERE username=%s",
            (username,))
        saved_images = cursor.fetchone()
        if saved_images[0]:
            saved_images = saved_images[0] + "," + base64.b64encode(image_data).decode("utf-8")
        else:
            saved_images = base64.b64encode(image_data).decode("utf-8")

        cursor.execute(
            "UPDATE db SET saved_images=%s WHERE username=%s",
            (saved_images, username))
        db_connection.commit()
        st.success("Image saved successfully!")
    except mysql.connector.Error as err:
        st.warning(f"An error occurred while saving image: {err}")

# Function for cartoonization
def calculate_ssim(img1, img2):
    if img1.shape != img2.shape:
        raise ValueError("Images must have the same dimensions")

    img1_gray = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    img2_gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    ssim_value, _ = ssim(img1_gray, img2_gray, full=True)
    dssim_value = 1 - ssim_value
    return ssim_value, dssim_value

def calculate_psnr(img1, img2):
    if img1.shape != img2.shape:
        raise ValueError("Images must have the same dimensions")

    mse = np.mean((img1 - img2) ** 2)
    psnr = 10 * np.log10((255 ** 2) / mse)
    return psnr, mse

def cartoonization(img, cartoon):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if cartoon == "Pencil Sketch":
        value = st.sidebar.slider('Tune the brightness of your sketch (the higher the value, the brighter your sketch)',
                                  0.0, 300.0, 250.0)
        kernel = st.sidebar.slider(
            'Tune the boldness of the edges of your sketch (the higher the value, the bolder the edges)', 1, 99, 25,
            step=2)

        gray_blur = cv2.GaussianBlur(gray, (kernel, kernel), 0)

        cartoon = cv2.divide(gray, gray_blur, scale=value)
        return cartoon

    if cartoon == "Detail Enhancement":
        smooth = st.sidebar.slider(
            'Tune the smoothness level of the image (the higher the value, the smoother the image)', 3, 99, 5, step=2)
        kernel = st.sidebar.slider('Tune the sharpness of the image (the lower the value, the sharper it is)', 1, 21, 3,
                                   step=2)
        edge_preserve = st.sidebar.slider(
            'Tune the color averaging effects (low: only similar colors will be smoothed, high: dissimilar color will be smoothed)',
            0.0, 1.0, 0.5)

        gray = cv2.medianBlur(gray, kernel)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                      cv2.THRESH_BINARY, 9, 9)

        color = cv2.detailEnhance(img, sigma_s=smooth, sigma_r=edge_preserve)
        cartoon = cv2.bitwise_and(color, color, mask=edges)
        return cartoon

    if cartoon == "Pencil Edges":
        kernel = st.sidebar.slider('Tune the sharpness of the sketch (the lower the value, the sharper it is)', 1, 99,
                                   25, step=2)
        laplacian_filter = st.sidebar.slider(
            'Tune the edge detection power (the higher the value, the more powerful it is)', 3, 9, 3, step=2)
        noise_reduction = st.sidebar.slider(
            'Tune the noise effects of your sketch (the higher the value, the noisier it is)', 10, 255, 150)

        gray = cv2.medianBlur(gray, kernel)
        edges = cv2.Laplacian(gray, -1, ksize=laplacian_filter)

        edges_inv = 255 - edges

        dummy, cartoon = cv2.threshold(edges_inv, noise_reduction, 255, cv2.THRESH_BINARY)
        return cartoon

    if cartoon == "Bilateral Filter":
        smooth = st.sidebar.slider(
            'Tune the smoothness level of the image (the higher the value, the smoother the image)', 3, 99, 5, step=2)
        kernel = st.sidebar.slider('Tune the sharpness of the image (the lower the value, the sharper it is)', 1, 21, 3,
                                   step=2)
        edge_preserve = st.sidebar.slider(
            'Tune the color averaging effects (low: only similar colors will be smoothed, high: dissimilar color will be smoothed)',
            1, 100, 50)

        gray = cv2.medianBlur(gray, kernel)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                      cv2.THRESH_BINARY, 9, 9)

        color = cv2.bilateralFilter(img, smooth, edge_preserve, smooth)
        cartoon = cv2.bitwise_and(color, color, mask=edges)
        return cartoon
    # Add other cartoonization styles as needed

# Streamlit app code
if st.session_state.is_logged_in:
    st.title("Cartoon Craft Web Application")
    st.sidebar.subheader("Navigation")
    page = st.sidebar.selectbox("", ["Cartoonize Your Image","View Saved Images"])

    if page == "Cartoonize Your Image":
        st.subheader("Cartoonize Your Image")

        # Retrieve the username from the login session
        username_input = st.session_state.logged_in_username

        cursor.execute("SELECT profile_photo FROM db WHERE username=%s", (username_input,))
        profile_photo_data = cursor.fetchone()

        if profile_photo_data is not None and profile_photo_data[0] is not None:
            st.sidebar.image(profile_photo_data[0], width=150, caption=f"Profile Photo - {username_input}")
        else:
            st.sidebar.text("No profile photo available")
            # ... (code for displaying profile photo remains unchanged)

        file = st.sidebar.file_uploader("Please upload an image file", type=["jpg", "png"])


        if file is None:
            st.text("You haven't uploaded an image file")
        else:
            image = Image.open(file)
            img = np.array(image)

            option = st.sidebar.selectbox(
                'Which cartoon filters would you like to apply?',
                ('Pencil Sketch', 'Detail Enhancement', 'Pencil Edges', 'Bilateral Filter'))

            st.text("Your original image")
            st.image(image, use_column_width=True)

            st.text("Your cartoonized image")
            progress = st.progress(0)
            status_text = st.empty()

            for i in range(101):
                progress.progress(i)
                status_text.text(f"Cartoonizing ({option})... {i}%")
                time.sleep(0.05)

            st.success(f"{option} Cartoonization complete!")

            cartoon = cartoonization(img, option)

            if cartoon is not None and isinstance(cartoon, np.ndarray):
                cartoon = cartoon.astype(np.uint8)
                cartoon_pil = Image.fromarray(cartoon)
                st.image(cartoon_pil, use_column_width=True)

                compressed_image = cv2.cvtColor(cartoon, cv2.COLOR_RGB2BGR)
                psnr_value, mse_value = calculate_psnr(img, compressed_image)
                ssim_value, dssim_value = calculate_ssim(img, compressed_image)

                st.subheader("Image Quality Metrics")

                if st.button("Calculate PSNR"):
                    st.write(f"PSNR: {psnr_value:.2f} dB")

                if st.button("Calculate MSE"):
                    st.write(f"MSE: {mse_value:.2f}")

                if st.button("Calculate SSIM"):
                    st.write(f"SSIM: {ssim_value:.4f}")

                if st.button("Calculate DSSIM"):
                    st.write(f"DSSIM: {dssim_value:.4f}")

                # Save button to save the cartoonized image
                if st.button("Save Image"):
                    save_image(username_input, cv2.imencode('.png', cv2.cvtColor(cartoon, cv2.COLOR_RGB2BGR))[1].tobytes())

                if st.sidebar.button("Logout"):
                    st.session_state.is_logged_in = False

    elif page == "View Saved Images":
        st.header("View Saved Images")

        # Retrieve the username from the login session
        username_input = st.session_state.logged_in_username

        cursor.execute("SELECT saved_images FROM db WHERE username=%s", (username_input,))
        saved_images_data = cursor.fetchone()
        saved_images = saved_images_data[0] if saved_images_data and saved_images_data[0] else ""
        saved_images_list = saved_images.split(',')

        if saved_images_list:
            st.subheader("Saved Images")
            for index, saved_image_data in enumerate(saved_images_list):
                image_data = base64.b64decode(saved_image_data)
                image = Image.open(BytesIO(image_data))
                st.image(image, caption=f"Saved Image {index + 1}", use_column_width=True)
                download_button = st.markdown(
                    f'<a href="data:application/octet-stream;base64,{saved_image_data}" '
                    f'download="saved_image_{index + 1}.png">Download Saved Image {index + 1}</a>',
                    unsafe_allow_html=True
                )
        else:
            st.write("No saved images found.")
        if st.sidebar.button("Logout"):
            st.session_state.is_logged_in = False

else:
    st.title('Cartoon Craft Web Application')

    # Display the navigation links
    st.markdown("""
        <style>
            .item {
                display: flex;
                justify-content: space-between;
                list-style: none;
                padding: 0;
            }
            .item a {
                text-decoration: none;
                margin: 10px;
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 5px;
                color: #333;
            }
        </style>
        <div class="item">
            <a href="?page=home" target="_self">&#127968; Home</a>
            <a href="?page=login" target="_self">&#128274; Login</a>
            <a href="?page=register" target="_self">&#128221; Register</a>
            <a href="?page=images" target="_self">&#128247; Images</a>
            <a href="?page=logout" target="_self">&#128682; Logout</a>
        </div>
    """, unsafe_allow_html=True)

    # Get the current page
    current_page = st.query_params.get("page", "home")

    # Implement the selected functionality based on the current page
    if current_page == "home":
        with open(r"C:\Users\santh\PycharmProjects\psnr\index.html", "r", encoding="utf-8") as html_file:
            html_content = html_file.read()

        # Read CSS content from file
        with open(r"C:\Users\santh\PycharmProjects\psnr\style.css", "r", encoding="utf-8") as css_file:
            css_content = css_file.read()

        # Use Streamlit's st.markdown to render HTML content
        st.markdown(html_content, unsafe_allow_html=True)

        # Use Streamlit's st.markdown to inject CSS styles
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

    elif current_page == "login":
        st.header("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if authenticate(username, password):
                st.success("Login successful!")
                st.session_state.is_logged_in = True
                st.session_state.logged_in_username = username  # Set the logged-in username in the session state
            else:
                st.warning("Invalid login credentials. Please Register")

    elif current_page == "register": # Register
        st.header("Register")
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        email = st.text_input("Email")
        dob = st.date_input("Date of Birth", datetime.date(year=2005, month=1, day=31))
        occupation = st.text_input("Occupation (Optional)")

        profile_photo = st.file_uploader("Upload Profile Photo", type=["png"])

        if profile_photo is not None and profile_photo.type in ["image/png"]:
            try:
                # Read profile photo data
                profile_photo_data = profile_photo.read()
                # Display the uploaded profile photo
                st.image(profile_photo, caption="Uploaded Profile Photo", use_column_width=True)
            except Exception as e:
                st.warning(f"Error reading the profile photo: {e}")
        else:
            st.warning("Please upload a valid PNG profile photo.")
            profile_photo_data = None
        if st.button("Register"):
            try:
                if not (new_username and new_password and confirm_password and email and dob):
                    raise ValueError("All fields are required. Please fill in all the details.")

                if len(new_password) < 8:
                    raise ValueError("Password must be at least 8 characters long.")

                if not email.endswith('@gmail.com'):
                    raise ValueError("Invalid email. Please enter a valid Gmail address.")

                profile_photo_data = profile_photo.read() if profile_photo is not None else None
                register(new_username, new_password, email, dob, occupation, profile_photo_data)

            except ValueError as e:
                st.warning(str(e))
    elif current_page == "images":
        st.header("Sample Images")

        # Sample image URLs
        sample_image_urls = [
            r"C:\Users\santh\OneDrive\Documents\Major Project\Detail Enhancement.jpg",
            r"C:\Users\santh\OneDrive\Documents\Major Project\pencil sketch.jpg",
            r"C:\Users\santh\OneDrive\Documents\Major Project\Bilateral Filter.jpg",
            r"C:\Users\santh\OneDrive\Documents\Major Project\penciledge.jpg"
        ]


        # Display animated image slideshow
        @st.cache_data
        def show_image(index):
            image_path = sample_image_urls[index]
            image = Image.open(image_path)
            st.image(image, caption="Sample Image", use_column_width=True)


        index = st.session_state.get("index", 0)

        if st.button("Next"):
            index = (index + 1) % len(sample_image_urls)

        st.session_state.index = index
        show_image(index)

    elif current_page == "logout":
        st.markdown('<meta http-equiv="refresh" content="0;URL=\'?page=home\'" />', unsafe_allow_html=True)
        st.title("Logged out. Redirecting to Home...")
