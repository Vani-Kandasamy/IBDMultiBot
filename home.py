import pandas as pd
import streamlit as st
from datetime import datetime
import authlib


IMAGE_ADDRESS = "https://aboutibs.org/wp-content/uploads/sites/13/Diet-and-IBS-768x512.jpg"

# web app
st.title("IBD Control Helper")

st.image(IMAGE_ADDRESS, caption = "IBD Nutrition Importance")

if not st.experimental_user.is_logged_in:
    if st.button("Log in with Google", type="primary", icon=":material/login:"):
        st.login()
else:
    # Display user name
    st.html(f"Hello, <span style='color: orange; font-weight: bold;'>{st.experimental_user.name}</span>!")
    
    # Documentation for each key
    selected_keys = ['email', 'name', 'picture']
    # Extract the key-value pairs from the dictionary
    selected_data = {key: st.experimental_user[key] for key in selected_keys}

    # Convert the dictionary to a DataFrame
    df = pd.DataFrame([selected_data])

    
    st.subheader("User Information", divider=True)
    # Create the DataFrame
   

    # Display the DataFrame in Streamlit
    st.dataframe(df, hide_index=True)

    if st.button("Log out", type="secondary", icon=":material/logout:"):
        st.logout()