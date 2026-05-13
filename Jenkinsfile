pipeline {
    agent any

    environment {
        IMAGE_NAME = 'demo-api'
        IMAGE_TAG = 'v2'
        CONTAINER_NAME = 'demo-api'
        NETWORK_NAME = 'app_net'
        HOST_PORT = '3000'
        CONTAINER_PORT = '8000'
    }

    stages {
        stage('拉取代码') {
            steps {
                checkout scm
            }
        }

        stage('查看文件') {
            steps {
                sh '''
                echo "当前文件："
                ls -lah
                test -f app.py
                test -f Dockerfile
                '''
            }
        }

        stage('确认网络') {
            steps {
                sh '''
                docker network inspect ${NETWORK_NAME} >/dev/null 2>&1 || docker network create ${NETWORK_NAME}
                '''
            }
        }

        stage('构建镜像') {
            steps {
                sh '''
                docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
                '''
            }
        }

        stage('替换业务容器') {
            steps {
                sh '''
                docker rm -f ${CONTAINER_NAME} || true

                docker run -d \
                  --name ${CONTAINER_NAME} \
                  --restart=unless-stopped \
                  --network ${NETWORK_NAME} \
                  -p ${HOST_PORT}:${CONTAINER_PORT} \
                  ${IMAGE_NAME}:${IMAGE_TAG}
                '''
            }
        }

        stage('检查服务') {
            steps {
                sh '''
                sleep 5
                docker ps | grep ${CONTAINER_NAME}

                echo "检查直连端口："
                curl -fsS http://127.0.0.1:${HOST_PORT}/ | head -c 200 || true

                echo
                echo "检查 Nginx 入口："
                curl -fsS http://127.0.0.1/ | head -c 200 || true
                echo
                '''
            }
        }
    }

    post {
        success {
            echo '部署成功：业务容器已更新，Nginx 入口保持不变'
        }
        failure {
            echo '部署失败：请查看控制台输出'
        }
    }
}
