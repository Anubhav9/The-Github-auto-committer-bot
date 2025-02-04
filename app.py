import base64
import json
import os
import logging
import datetime
from crypt import methods, crypt
import threading

from cryptography.fernet import Fernet

from flask import Flask, request, render_template, redirect
import requests
import mysql.connector
import schedule
import time

import configs

app = Flask(__name__)

logging.getLogger().setLevel(logging.INFO)

full_repo_name_post_creation = "Hello, all Lazy People"


crypt = Fernet(os.environ.get("FERNET_KEY"))

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/register-user", methods=["POST"])
def register_user():
    USER_TOKEN = request.form.get("token")
    encrypted_token = crypt.encrypt(USER_TOKEN.encode())
    formulated_body_json = {
        "name": configs.HARDCODED_REPOSITORY_NAME,
        "description": "Just fooling along for fun - No harm intended",
        "private": "true"
    }
    COMPLETE_API_URL = f"{configs.GITHUB_API_URL}/user/repos"
    headers = {
        "Authorization": "Bearer " + USER_TOKEN
    }
    logging.info(f"Sending POST API Request to {COMPLETE_API_URL}")
    response = requests.post(url=COMPLETE_API_URL, headers=headers, json=formulated_body_json)
    if response.status_code == 201:
        logging.info("Repository has been successfully created")
        full_repo_name_post_creation = response.json().get("owner").get("login")
        owner_name = full_repo_name_post_creation
        db_connection_object = mysql.connector.connect(
            host=os.environ.get("MYSQL_HOST"),
            port=os.environ.get("MYSQL_PORT"),
            user=os.environ.get("MYSQL_USER"),
            password=os.environ.get("MYSQL_PASSWORD"),
            database=os.environ.get("MYSQL_DATABASE")
        )
        if db_connection_object.is_connected():
            logging.info("Connected to MySQL Database")
            cursor = db_connection_object.cursor()
            INSERT_QUERY = f"INSERT into all_registered_users (username,date_created,to_end_date,token,is_active,file_sha) VALUES ('{owner_name}','{datetime.datetime.today()}','{datetime.datetime.today() + datetime.timedelta(days=7)}','{encrypted_token.decode('utf-8')}',1,'')"
            cursor.execute(INSERT_QUERY)
            db_connection_object.commit()
            cursor.close()
            db_connection_object.close()
        else:
            logging.info("Some error occurred while connecting to MySQL Database")
            logging.error(json.dumps({
                "message": "Repository created successfully but some error occurred while connecting to MySQL Database"}))
            return render_template("error_page.html")

        response_status_code_for_base_file_creation = create_readme_file(owner_name, USER_TOKEN)
        if response_status_code_for_base_file_creation.status_code == 201:
            generated_file_sha=response_status_code_for_base_file_creation.json().get("content").get("sha")
            db_connection_object = mysql.connector.connect(
                host=os.environ.get("MYSQL_HOST"),
                port=os.environ.get("MYSQL_PORT"),
                user=os.environ.get("MYSQL_USER"),
                password=os.environ.get("MYSQL_PASSWORD"),
                database=os.environ.get("MYSQL_DATABASE")
            )
            if db_connection_object.is_connected():
                logging.info("Connected to MySQL Database")
                cursor = db_connection_object.cursor()
                UPDATE_QUERY=f"UPDATE all_registered_users SET file_sha='{generated_file_sha}' WHERE username='{owner_name}'"
                cursor.execute(UPDATE_QUERY)
                db_connection_object.commit()
                cursor.close()
                db_connection_object.close()

            return render_template("index.html",
                                   message="Congratulations! Take a break while I do the hard work for you")
        else:
            logging.error(json.dumps({"ERR_STATUS_CODE": response_status_code_for_base_file_creation.status_code,
                                      "message": "Some error occurred while creating the file in the repository"}))
            return render_template("error_page.html")
    else:
        logging.info(f"Eror Message: {response.json()}")
        logging.info("Some error occurred while creating the repository")
        logging.error(json.dumps(
            {"ERR_STATUS_CODE": response.status_code, "message": "Some error occurred while creating the repository"})
        )
        return render_template("error_page.html")


def create_readme_file(github_username, github_token):
    formatted_body = {
        "message": configs.FIRST_COMMIT_MESSAGE,
        "content": base64.b64encode(configs.FIRST_COMMIT_CONTENT.encode()).decode(),
    }
    headers = {
        "Authorization": "Bearer " + github_token
    }
    URL_FOR_FILE_CREATION = configs.GITHUB_API_URL + f"/repos/{github_username}/{configs.HARDCODED_REPOSITORY_NAME}/contents/readme.md"
    logging.info(f"{URL_FOR_FILE_CREATION}")
    response = requests.put(url=URL_FOR_FILE_CREATION, headers=headers, json=formatted_body)
    return response


def do_random_commit_on_readme_file(github_username,github_token,file_sha):
    formatted_body = {
        "message": configs.FIRST_COMMIT_MESSAGE,
        "content": base64.b64encode(configs.FIRST_COMMIT_CONTENT.encode()).decode(),
        "sha":file_sha
    }
    headers={
        "Authorization": "Bearer " + github_token
    }
    URL_FOR_FILE_CREATION = configs.GITHUB_API_URL + f"/repos/{github_username}/{configs.HARDCODED_REPOSITORY_NAME}/contents/readme.md"

    response = requests.put(url=URL_FOR_FILE_CREATION, headers=headers, json=formatted_body)
    if response.status_code==200:
        logging.info(f"Successfully made a dummy commit for user {github_username}")

    else:
        logging.error(f"Status Code::{response.status_code}")
        logging.error(f"Something went wrong while having the dummy commit for user {github_username}")


def run_the_schedule_script():
    db_connection_object = mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST"),
        port=os.environ.get("MYSQL_PORT"),
        user=os.environ.get("MYSQL_USER"),
        password=os.environ.get("MYSQL_PASSWORD"),
        database=os.environ.get("MYSQL_DATABASE")
    )
    if db_connection_object.is_connected():
        logging.info("Connected to MySQL Database")
        cursor = db_connection_object.cursor()
        FETCH_QUERY=f"SELECT username,token,file_sha from all_registered_users WHERE is_active=1"
        cursor.execute(FETCH_QUERY)
        result=cursor.fetchall()
        logging.info(f"Result is {result}")
        for i in range(0,len(result)):
            git_username=result[i][0]
            git_token=result[i][1]
            git_token=crypt.decrypt(git_token.encode()).decode()
            file_sha=result[i][2]
            do_random_commit_on_readme_file(git_username,git_token,file_sha)
        db_connection_object.commit()
        cursor.close()
        db_connection_object.close()


schedule.every().day.at("12:00").do(run_the_schedule_script)

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    schedule_thread = threading.Thread(target=run_schedule, daemon=True)
    schedule_thread.start()
    app.run(port=3009, host='0.0.0.0')

