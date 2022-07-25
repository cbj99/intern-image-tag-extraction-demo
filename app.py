from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash
from werkzeug.utils import secure_filename
import json
import os
import requests
import time

# prediction_endpoint
prediction_endpoint = ""
# prediction_key
prediction_key = ""
# prediction_id
prediction_resource_id = ""

# training_endpoint
training_endpoint = ""
# training_key
training_key = ""

# custom vision projectID
project_id = ""

# get the latest iteration(model)
get_iterations_url = training_endpoint + "customvision/v3.3/training/projects/"+ project_id +"/iterations"
training_headers = {
        'Training-Key': training_key,
}
iteration_response = requests.get(get_iterations_url, headers=training_headers)
iteration_list = iteration_response.json()

# name of the model to evaluate against
# published_name = "Iteration1"
published_name = iteration_list[-1]["publishName"]
# print(published_name)

dirname = os.path.dirname(__file__)
app = Flask(__name__)
# This is the path to the upload directory
app.config['UPLOAD_FOLDER'] = 'uploads/'
# These are the extension that we are accepting to be uploaded
app.config['ALLOWED_EXTENSIONS'] = set(['pdf', 'png', 'jpg', 'jpeg', 'gif'])
# For a given file, return whether it's an allowed type or not
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'


def allowed_file(filename):
  return '.' in filename and \
      filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']


def getJSON(image_data):

    text_recognition_url = prediction_endpoint + "customvision/v3.0/Prediction/" + project_id + "/classify/iterations/" + published_name + "/image"
    headers = {
        'Prediction-key': prediction_key,
        'Content-Type': 'application/octet-stream'
    }
    response = requests.post(text_recognition_url,
                             headers=headers, data=image_data)
    
    response.raise_for_status()
    analysis = response.json()
    response.close()
    # print(analysis)
    return analysis


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(dirname, filename)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/uploader', methods=['POST'])
def upload_file():

    if 'file[]' not in request.files:
        return redirect(request.url)
    # Get the name of the uploaded files
    uploaded_files = request.files.getlist("file[]")
    new_tag = request.form.get("newTag")
    new_tag_ID = ""
    table=[]

    # if there is a new tag, retrain the model
    if(new_tag):
        flash('New tag added!')
        flash(f'New tag: {new_tag}')
        create_new_tag_url = training_endpoint + "customvision/v3.3/training/projects/"+ project_id + "/tags?name=" + new_tag
        create_new_tag_response = requests.post(create_new_tag_url, headers=training_headers)
        reponse_json = create_new_tag_response.json()
        new_tag_ID = reponse_json["id"]

        for file in uploaded_files:
        
            if file.filename == '':
                return redirect(request.url)
            if file and allowed_file(file.filename):
                # add the provided images to the set of training images
                add_image_url = training_endpoint + "customvision/v3.3/training/projects/"+ project_id + "/images?tagIds=" + new_tag_ID
                image_headers = {
                    'Training-Key': training_key,
                    'Content-Type': 'application/octet-stream'
                }   
                add_image_response = requests.post(add_image_url, headers=image_headers, data=file)
                add_image_response.raise_for_status()

                result = [file.filename, new_tag] 
                table.append(result)
                
        # get the count of image with this tag, if >= 5, retrain
        count_url = training_endpoint + "customvision/v3.3/training/projects/"+ project_id + "/images/count?taggingStatus=Tagged&tagIds=" + new_tag_ID
        count_response = requests.get(count_url, headers=training_headers)
        count_response.raise_for_status()
    
        if(count_response.json()>=5):
            # retrain the model and publish new iteration
            train_url = training_endpoint + "customvision/v3.3/training/projects/"+ project_id + "/train"
            train_response = requests.post(train_url, headers=training_headers)
            train_response.raise_for_status()
            result = train_response.json()

            # POST {Endpoint}/customvision/v3.3/training/projects/{projectId}/iterations/{iterationId}/publish?publishName={publishName}&predictionId={predictionId}
            new_iteration_id = result["id"]
            print ("Training...")

            while True:
                get_iteration_url = training_endpoint + "customvision/v3.3/training/projects/"+ project_id + "/iterations/" + new_iteration_id
                get_iteration_response = requests.get(get_iteration_url, headers=training_headers)
                result = get_iteration_response.json()
                print ("Waiting 10 seconds...")
                time.sleep(10)
                if(result["status"] == "Completed"):
                    break
            
            publish_url = training_endpoint + "customvision/v3.3/training/projects/"+ project_id + "/iterations/" + new_iteration_id + "/publish?publishName=Latest&predictionId=" + prediction_resource_id
            publish_response = requests.post(publish_url, headers=training_headers)
            publish_response.raise_for_status()

    # if there is no new tag, predict
    else:
        
        for file in uploaded_files:
        
            if file.filename == '':
                return redirect(request.url)
            if file and allowed_file(file.filename):
                analysis = getJSON(file)
                
                result = [file.filename, analysis['predictions'][0]['tagName']] 
                table.append(result)

    # saveAsCSV(table)
    return render_template('home.html', data=table)
    # return redirect('/uploads/'+'output.csv') 
        

if __name__ == '__main__':
    app.run(debug=True)
