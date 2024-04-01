#!/bin/bash
set -e

# Postifx chroot requires resolv.conf, use the VPC resolver
echo 'nameserver 169.254.169.253' >> /var/spool/postfix/etc/resolv.conf

if [ "${ENABLE_HELO_DOMAIN_RESTRICTIONS}" == "True" ];then
 CHECK_HELO_DEFAULT_ACTION="reject"
else
 CHECK_HELO_DEFAULT_ACTION="permit"
fi

# Postfix Configuration
postconf -e "relayhost = [${SES_SMTP_ENDPOINT}]:587" \
    "smtp_tls_key_file = /etc/postfix/sslcert.key" \
    "smtp_tls_cert_file = /etc/postfix/sslcert.pem" \
    "smtp_sasl_auth_enable = yes" \
    "smtp_sasl_security_options = noanonymous" \
    "smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd_maps" \
    "smtp_use_tls = yes" \
    "smtp_tls_security_level = encrypt" \
    "smtp_tls_note_starttls_offer = yes" \
    "smtpd_banner = ESMTP ***** UCE NOT ACCEPTED *****" \
    "smtpd_helo_required = yes" \
    "smtpd_helo_restrictions = check_helo_access hash:/etc/postfix/smtpd_helo_access_maps, ${CHECK_HELO_DEFAULT_ACTION}" \
    "smtpd_delay_reject = yes" \
    "disable_vrfy_command = yes" \
    "maillog_file = /dev/stdout" \
    "mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128 ${ALLOWED_CLIENTS}"
    
# Setup Postfix SASL Authentication
echo "[${SES_SMTP_ENDPOINT}]:587 ${SES_SMTP_USERNAME}:${SES_SMTP_PASSWORD}" > /etc/postfix/sasl_passwd_maps
postmap -v hash:/etc/postfix/sasl_passwd_maps
chown -v root:root /etc/postfix/sasl_passwd_maps /etc/postfix/sasl_passwd_maps.db
chmod -v 600 /etc/postfix/sasl_passwd_maps /etc/postfix/sasl_passwd_maps.db

# Setup Postfix check_helo_access.
echo -n > /etc/postfix/smtpd_helo_access_maps
for domain in ${ALLOWED_HELO_DOMAINS};do
    echo "${domain} OK" >> /etc/postfix/smtpd_helo_access_maps
done
postmap -v /etc/postfix/smtpd_helo_access_maps
chown -v root:root /etc/postfix/smtpd_helo_access_maps /etc/postfix/smtpd_helo_access_maps.db
chmod -v 600 /etc/postfix/smtpd_helo_access_maps /etc/postfix/smtpd_helo_access_maps.db

#Start Postfix
exec /usr/sbin/postfix -c /etc/postfix start-fg