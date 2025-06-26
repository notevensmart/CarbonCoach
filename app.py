'''Manages the Gradio interface

Connects the UI inputs to backend logic (predictor, generator)

Defines how users interact with the system

Controls the overall workflow '''
import gradio as gr
import requests

import requests
climatiq_api_key = "SCCDV0RCQD1AV7RN7SA3P8RDAR"


def fetch_supported_countries():
    url = "https://api.climatiq.io"
    headers = {
        "Authorization": f"Bearer {climatiq_api_key}"  
    }
    try:
        response = requests.get(url, headers=headers)
        print("Status:", response.status_code)
        print("Body:", response.text)
        if response.status_code == 200:
            all_regions = response.json()
            countries = [r for r in all_regions if r["type"] == "country"]
            return [(c["name"], c["id"]) for c in countries]  # (label, value)
        else:
            print("Failed to fetch regions")
    except Exception as e:
        print("Exception occurred:", e)
    
    return [("India", "IN"), ("United States", "US")]  # fallback default



def estimate_footprint(country, journal_input):
    # Placeholder logic
    return f"Based on your input from {country}, we estimate your carbon footprint..."

with gr.Blocks() as demo:
    gr.Markdown("# Welcome to CarbonCoach!")
    gr.Markdown("## Your personal carbon footprint tracker and coach")
    with gr.Row():
        with gr.Column():
            gr.Markdown("Select Which Country you are currently living in")
            country_dropdown = gr.Dropdown(
                label="Country",
                choices=fetch_supported_countries(),
                value="IN"

            )
           
            
        with gr.Column():
            gr.Markdown("### Input your journal text:")
            journal_input = gr.Textbox(label="Journal Text", placeholder="Tell us about your daily habits — "
            "how you travel, what you eat, and what your home life is like.")
            submit_button = gr.Button("Submit")
        with gr.Column():
            gr.Markdown("### Carbon Footprint Output:")
            output_text = gr.Textbox(label="Carbon Footprint", interactive=False) 
    submit_button.click(
        fn=estimate_footprint,
        inputs=[country_dropdown, journal_input],
        outputs=output_text
    )          
demo.launch(share=True, debug=True)
