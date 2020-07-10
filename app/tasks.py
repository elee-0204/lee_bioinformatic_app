#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 11:22:19 2020

@author: elee
"""
import sys
import os
# import time
# import shutil
from rq import get_current_job
from app import create_app, db
from app.models import Task
from app.processing import add_thisistest, add_thisisnttest, creating_R_figure
from app.s3_demo import list_files_s3, download_file_s3, upload_pdf_files, upload_processed_files
import boto3

app = create_app()
app.app_context().push()

from flask import current_app
# DOWNLOAD_FOLDER = os.path.abspath(os.path.dirname(__file__)) + '/downloads/'

def _set_task_progress(progress):
    job = get_current_job()
    if job:
        job.meta['progress'] = progress
        job.save_meta()
        task = Task.query.get(job.get_id())
        # task.user.add_notification('task_progress', {'task_id': job.get_id(),
        #                                               'progress': progress})
        if progress >= 100:
            task.complete = True
        db.session.commit()


def process_files(type):
    try:
        _set_task_progress(0)
        i = 0
        # shutil.rmtree(current_app.config['DOWNLOAD_FOLDER'])
        # os.makedirs(current_app.config['DOWNLOAD_FOLDER'], exist_ok = True) 
        filenames = list_files_s3("leelab")
        total_files = len(filenames)
        s3 = boto3.resource('s3')
        bucket_to_delete = s3.Bucket("leelab-processed")
        bucket_to_delete.objects.all().delete()
        for filename in filenames:
            output_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], filename)
            # folder_to_save = os.path.join(UPLOAD_FOLDER, filename)
            file = download_file_s3(filename, "leelab")
            if type=="one":
                add_thisistest(filename)
            elif type=="two":
                add_thisisnttest(filename)
            upload_processed_files(output_path, "leelab-processed", filename)
            i += 1
            _set_task_progress(100 * (i // total_files)) 
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
        
        
def graph_figures():
    try:
        _set_task_progress(0)
        i = 0
        # setting up the bucket
        filenames = list_files_s3("leelab")
        total_files = len(filenames)
        s3 = boto3.resource('s3')
        bucket_to_delete = s3.Bucket("leelab-processed")
        bucket_to_delete.objects.all().delete()
        # R file commands
        for filename in filenames:
            # Variable number of args in a list
            output_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], filename)
            file = download_file_s3(filename, "leelab")
            # Args for creating R figure
            myfile = os.path.join(current_app.config['DOWNLOAD_FOLDER'], filename)
            filename = filename.rsplit( ".", 1 )[ 0 ]
            filepath = os.path.join(current_app.config['DOWNLOAD_FOLDER'], f"graphs_{filename}.pdf")
            # creating the figure in R studio
            creating_R_figure(myfile, filepath)
            # uploading to the bucket
            upload_pdf_files(filepath, "leelab-processed", f"graphs_{filename}.pdf")
            # updating task progrress
            i += 1
            _set_task_progress(100 * (i // total_files)) 
    except:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
         