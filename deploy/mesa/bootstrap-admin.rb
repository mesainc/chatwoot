# Run once with a private JSON file: bundle exec rails runner bootstrap-admin.rb /tmp/admin.json
require 'json'

raise 'Installation already has users; use normal administrator controls' if User.exists?
input = JSON.parse(File.read(ARGV.fetch(0)))
user, account = AccountBuilder.new(
  account_name: 'Mesa',
  user_full_name: input.fetch('name'),
  email: input.fetch('email'),
  user_password: input.fetch('password'),
  super_admin: true,
  confirmed: true
).perform
Redis::Alfred.delete(Redis::Alfred::CHATWOOT_INSTALLATION_ONBOARDING)
raise 'Administrator bootstrap failed' unless user.confirmed? && SuperAdmin.exists?(id: user.id) && account.account_users.find_by!(user: user).administrator?
puts 'Mesa account and confirmed administrator created; public installation onboarding disabled.'
