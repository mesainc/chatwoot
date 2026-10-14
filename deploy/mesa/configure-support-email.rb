# Run after support-domain DNS verification and scoped sending-key installation.
email = ENV.fetch('SUPPORT_EMAIL', 'vendeuganhou@suporte.mesa.tech')
domain = email.split('@').last
password = ENV.fetch('SUPPORT_SMTP_PASSWORD')
raise 'Support SMTP password is empty' if password.empty?

ActiveRecord::Base.transaction do
  account = Account.find(1)
  account.update!(domain: domain)
  channel = Channel::Email.find(1)
  if channel.email != email && channel.inbox.conversations.exists?
    raise 'Review existing inbox conversations before changing the support address'
  end
  channel.update!(
    email: email, forward_to_email: email, provider: nil, provider_config: {},
    imap_enabled: false, imap_address: '', imap_login: '', imap_password: '', imap_port: 0,
    smtp_enabled: true, smtp_address: 'smtp.resend.com', smtp_port: 465,
    smtp_domain: domain, smtp_login: 'resend', smtp_password: password,
    smtp_enable_ssl_tls: true, smtp_enable_starttls_auto: false,
    smtp_authentication: 'login', smtp_openssl_verify_mode: 'peer',
    verified_for_sending: true
  )
  channel.inbox.update!(name: 'Vendeu Ganhou — Suporte')
  config = InstallationConfig.find_or_initialize_by(name: 'MAILER_INBOUND_EMAIL_DOMAIN')
  config.value = domain
  config.save!
end
GlobalConfig.clear_cache
puts 'Dedicated support email configured; personal Gmail intake disabled.'
