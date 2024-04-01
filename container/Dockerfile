# build args
ARG DEBIAN_FRONTEND=noninteractive
ARG POSTFIX_SMTP_PORT
ARG BUILD_PLATFORM

FROM --platform=${BUILD_PLATFORM} ubuntu:jammy

# environment:
ENV TZ=Etc/UTC

# Configure base OS
RUN apt-get update
# Install dependencies
RUN apt-get -y install tzdata postfix libsasl2-modules
# dev packages:
#RUN apt-get -y install net-tools vim

# Generate self-signed SSL Certificate to use with SES endpoint 
RUN openssl req -new -x509 -days 3650 -nodes -subj '/CN=SESRelayDemo/O=SESRelayDemo/C=US' -out /etc/postfix/sslcert.pem -keyout /etc/postfix/sslcert.key

WORKDIR /app

COPY start-postfix.sh start-postfix.sh
RUN chmod +x start-postfix.sh

# set ownership of workdir
RUN chown -R nobody:nogroup /app

# Configure ports - storescp, stunnel -> storescp
EXPOSE ${POSTFIX_SMTP_PORT}

CMD ["/app/start-postfix.sh"]