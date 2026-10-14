# Idempotent staff application name; no enterprise feature flags are changed.
config = InstallationConfig.find_or_initialize_by(name: 'INSTALLATION_NAME')
config.value = 'Mesa Support'
config.save!
GlobalConfig.clear_cache
puts 'Mesa staff application name configured.'
