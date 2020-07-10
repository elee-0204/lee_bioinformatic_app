#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 11:22:19 2020

@author: elee
"""
import os
from flask import current_app
# from app.s3_demo import list_files_s3, download_file_s3, upload_file_s3, upload_processed_files
# import boto3
import subprocess

# from app import create_app

# app = create_app()
# app.app_context().push()

ALLOWED_EXTENSIONS = {'txt'}
# DOWNLOAD_FOLDER = os.path.abspath(os.path.dirname(__file__)) + '/downloads/'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def add_thisistest(filename):
    output_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], filename)
    output = open(output_path, "a+") 
    output.write(", this is a test") 
    output.close()
    
def add_thisisnttest(filename):
    output_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], filename)
    output = open(output_path, "a+") 
    output.write(", this isn't a test") 
    output.close()
    
def creating_R_figure(myfile, filepath):
    command ='Rscript'
    app_file_path = (os.path.dirname(os.path.abspath(__file__)))
    path2script = os.path.join(app_file_path, "Violin_Plot_Maker.R")
    args = [myfile, filepath]
    # Build subprocess command
    cmd = [command, path2script] + args
    # check_output will run the command and store to result
    subprocess.check_output(cmd, universal_newlines=True)