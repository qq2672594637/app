pipeline {
    agent any

    parameters {
        choice(
            name: 'ACTION',
            choices: ['deploy', 'rollback'],
            description: 'deploy = build and release latest code, rollback = restore previous image'
        )
    }

    environment {
        IMAGE_NAME = 'demo-api'
        CURRENT_TAG = 'current'
        PREVIOUS_TAG = 'previous'
        BUILD_TAG_NAME = "build-${BUILD_NUMBER}"
        CONTAINER_NAME = 'demo-api'
        NETWORK_NAME = 'app_net'
        HOST_PORT = '3000'
        CONTAINER_PORT = '8000'
    }

    stages {
        stage('Checkout') {
            when {
                expression { params.ACTION == 'deploy' }
            }
            steps {
                checkout scm
            }
        }

        stage('Show Files') {
            when {
                expression { params.ACTION == 'deploy' }
            }
            steps {
                sh '''
                echo "Current files:"
                ls -lah
                test -f app.py
                test -f Dockerfile
                '''
            }
        }

        stage('Prepare Network') {
            steps {
                sh '''
                docker network inspect ${NETWORK_NAME} >/dev/null 2>&1 || docker network create ${NETWORK_NAME}
                '''
            }
        }

        stage('Backup Current Image') {
            when {
                expression { params.ACTION == 'deploy' }
            }
            steps {
                sh '''
                if docker ps -a --format '{{.Names}}' | grep -Fx ${CONTAINER_NAME} >/dev/null 2>&1; then
                  RUNNING_IMAGE_ID=$(docker inspect -f '{{.Image}}' ${CONTAINER_NAME})
                  docker tag ${RUNNING_IMAGE_ID} ${IMAGE_NAME}:${PREVIOUS_TAG}
                  echo "Running container image saved as ${IMAGE_NAME}:${PREVIOUS_TAG}"
                elif docker image inspect ${IMAGE_NAME}:${CURRENT_TAG} >/dev/null 2>&1; then
                  docker tag ${IMAGE_NAME}:${CURRENT_TAG} ${IMAGE_NAME}:${PREVIOUS_TAG}
                  echo "Current image saved as ${IMAGE_NAME}:${PREVIOUS_TAG}"
                elif docker image inspect ${IMAGE_NAME}:v2 >/dev/null 2>&1; then
                  docker tag ${IMAGE_NAME}:v2 ${IMAGE_NAME}:${PREVIOUS_TAG}
                  echo "Legacy image ${IMAGE_NAME}:v2 saved as ${IMAGE_NAME}:${PREVIOUS_TAG}"
                else
                  echo "No previous running image exists yet, skip backup."
                fi
                '''
            }
        }

        stage('Build Image') {
            when {
                expression { params.ACTION == 'deploy' }
            }
            steps {
                sh '''
                docker build -t ${IMAGE_NAME}:${BUILD_TAG_NAME} .
                docker tag ${IMAGE_NAME}:${BUILD_TAG_NAME} ${IMAGE_NAME}:${CURRENT_TAG}
                '''
            }
        }

        stage('Deploy Current Image') {
            when {
                expression { params.ACTION == 'deploy' }
            }
            steps {
                sh '''
                docker rm -f ${CONTAINER_NAME} || true

                docker run -d \
                  --name ${CONTAINER_NAME} \
                  --restart=unless-stopped \
                  --network ${NETWORK_NAME} \
                  -p ${HOST_PORT}:${CONTAINER_PORT} \
                  ${IMAGE_NAME}:${CURRENT_TAG}
                '''
            }
        }

        stage('Rollback') {
            when {
                expression { params.ACTION == 'rollback' }
            }
            steps {
                sh '''
                if ! docker image inspect ${IMAGE_NAME}:${PREVIOUS_TAG} >/dev/null 2>&1; then
                  echo "No rollback image found: ${IMAGE_NAME}:${PREVIOUS_TAG}"
                  exit 1
                fi

                docker rm -f ${CONTAINER_NAME} || true

                docker run -d \
                  --name ${CONTAINER_NAME} \
                  --restart=unless-stopped \
                  --network ${NETWORK_NAME} \
                  -p ${HOST_PORT}:${CONTAINER_PORT} \
                  ${IMAGE_NAME}:${PREVIOUS_TAG}

                docker tag ${IMAGE_NAME}:${PREVIOUS_TAG} ${IMAGE_NAME}:${CURRENT_TAG}
                '''
            }
        }

        stage('Check Service') {
            steps {
                sh '''
                sleep 5
                docker ps | grep ${CONTAINER_NAME}

                echo "Check host port:"
                curl -fsS http://127.0.0.1:${HOST_PORT}/ | head -c 200 || true

                echo
                echo "Check Nginx entry:"
                curl -fsS http://127.0.0.1/ | head -c 200 || true
                echo
                '''
            }
        }
    }

    post {
        success {
            echo "Action ${params.ACTION} succeeded. Container ${CONTAINER_NAME} is running."
        }
        failure {
            echo "Action ${params.ACTION} failed. Check Console Output."
        }
    }
}
