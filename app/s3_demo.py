#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 30 21:16:06 2020

@author: elee
"""
import boto3
import botocore
from flask import current_app
import os 

def upload_file_s3(file_name, bucket):
    """
    Function to upload a file to an S3 bucket
    takes in a file and the bucket name and uploads the given file to our S3 bucket on AWS.
    """
    object_name = file_name
    s3_client = boto3.client('s3')
    response = s3_client.upload_file(file_name, bucket, object_name)
    # response = s3_client.upload_file_s3(file_name, bucket, object_name)

    return response


def upload_processed_files(file_path, bucket, file_name):
    """
    Function to upload a file to an S3 bucket
    takes in a file and the bucket name and uploads the given file to our S3 bucket on AWS.
    """    
    object_name = file_name
    s3_client = boto3.client('s3')
    response = s3_client.upload_file(file_path, bucket, object_name)
    # response = s3_client.upload_file_s3(file_name, bucket, object_name)

    return response

def download_file_s3(file_name, bucket):
    """
    Function to download a given file from an S3 bucket
    takes in a file name and a bucket and downloads it to a folder that we specify.
    """
    s3 = boto3.resource('s3')
    output = os.path.join(current_app.config['DOWNLOAD_FOLDER'], file_name)
    s3.Bucket(bucket).download_file(file_name, output)

    return output


def upload_pdf_files(file_path, bucket, file_name):
    """
    Function to upload a file to an S3 bucket
    takes in a file and the bucket name and uploads the given file to our S3 bucket on AWS.
    """    
    # object_name = file_name
    # s3_client = boto3.client('s3')
    # response = s3_client.upload_file(file_path, bucket, object_name, 
    #                                  ExtraArgs={'ContentType': 'application/pdf', 'ContentDisposition': 'inline'})
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket)
    bucket.upload_file(file_path, file_name, 
                       ExtraArgs={'ContentType': 'application/pdf', 'ContentDisposition': 'inline'})

    # response = s3_client.upload_file_s3(file_name, bucket, object_name)
    # return response



# my_object = bucket.Object('mykey')
# print(my_object.content_type)  

    # s3 = boto3.resource('s3')
    # output = f"/downloads/{file_name}"
    # s3.meta.client.download_file(bucket, file_name, output)
    # s3 = boto3.client('s3')
    # try:
    #     s3.Bucket(bucket).download_file(file_name,  os.path.join(current_app.config['DOWNLOAD_FOLDER'], file_name))
    # except botocore.exceptions.ClientError as e:
    #     if e.response['Error']['Code'] == "404":
    #         print("The object does not exist.")
    #     else:
    #         raise
        
    # return output


# def downloadDirectoryFroms3(bucketName,remoteDirectoryName):
#     s3_resource = boto3.resource('s3')
#     bucket = s3_resource.Bucket(bucketName) 
#     for object in bucket.objects.filter(Prefix = remoteDirectoryName):
#         if not os.path.exists(os.path.dirname(object.key)):
#             os.makedirs(os.path.dirname(object.key))
#         bucket.download_file(object.key,object.key)
        

def list_files_s3(bucket):
    """
    Function to list files in a given S3 bucket
    used to retrieve the files in our S3 bucket and list their names. We will use these names to download the files from our S3 buckets.
    """
    s3 = boto3.client('s3')
    contents = []
    filenames = []
    try:
        for item in s3.list_objects(Bucket=bucket)['Contents']:
            print(item)
            contents.append(item)
        for file in contents:
            filename = file.get('Key')
            filenames.append(filename)
    except Exception as e:
        pass

    return filenames