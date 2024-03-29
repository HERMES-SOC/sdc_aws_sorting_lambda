# Repo where this image's Dockerfile is maintained: https://github.com/HERMES-SOC/docker-lambda-base
ARG BASE_IMAGE=public.ecr.aws/w5r9l1c8/dev-swsoc-docker-lambda-base:latest

FROM ${BASE_IMAGE}

# Working Directory Arguments
ARG ROOT="/"
ARG FUNCTION_DIR="/lambda_function/"

COPY requirements.txt ${ROOT}

# Update pip and install setuptools
RUN pip install --upgrade pip setuptools

# Install requirements
RUN pip install -r requirements.txt

# Change working directory to /function
WORKDIR ${FUNCTION_DIR}

# Set Up Lambda Runtime Environment
RUN apt-get install -y curl && curl -Lo /usr/local/bin/aws-lambda-rie \
    https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie && \
    chmod +x /usr/local/bin/aws-lambda-rie

# Copy files from the source folder
COPY src/. ${FUNCTION_DIR}

# Set permissions for all files in function directory
RUN chmod -R 755 ${FUNCTION_DIR}
RUN chown -R 1000:1000 ${FUNCTION_DIR}

# Copy entry script into function director (Script is used distinguish dev/production mode)
COPY entry_script.sh ${FUNCTION_DIR}

# Set permissions for entry script
RUN chmod 755 ${FUNCTION_DIR}entry_script.sh
RUN chown 1000:1000 ${FUNCTION_DIR}entry_script.sh

# Change working directory to /function
WORKDIR ${FUNCTION_DIR}

# Runs entry script to decide wether to run function in local environment or in production environment
ENTRYPOINT [ "sh", "entry_script.sh" ]

# Runs lambda handler function
CMD [ "lambda.handler" ]