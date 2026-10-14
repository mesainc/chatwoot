# Run with the deployed Rails image: bundle exec rails runner /path/files.rb COMMAND [DIRECTORY].
# Pause web/worker writers before migration or snapshot. Never logs keys, filenames or signed URLs.
require 'digest'
require 'fileutils'
require 'json'
require 'net/http'
require 'pathname'
require 'securerandom'
require 'stringio'

Rails.logger.level = Logger::WARN

def inventory(service)
  service.bucket.objects.to_h { |object| [object.key, { 'etag' => object.etag, 'size' => object.size }] }
end

def remote_digest(service, key)
  digest = Digest::SHA256.new
  service.download(key) { |chunk| digest.update(chunk) }
  digest.hexdigest
end

def verify_snapshot(directory)
  manifest = JSON.parse(File.read(File.join(directory, 'manifest.json')))
  raise 'Unsupported storage snapshot' unless manifest.fetch('format') == 1

  manifest.fetch('objects').each_with_index do |object, index|
    raise 'Invalid snapshot object path' unless object.fetch('file') == format('objects/%08d', index)

    path = File.join(directory, object.fetch('file'))
    raise 'Snapshot size differs' unless File.size(path) == object.fetch('size')
    raise 'Snapshot checksum differs' unless Digest::SHA256.file(path).hexdigest == object.fetch('sha256')
  end
  objects = manifest.fetch('objects').index_by { |object| object.fetch('key') }
  manifest.fetch('blobs').each do |key, size, checksum, service_name|
    raise 'Snapshot has a non-OCI blob' unless service_name == 's3_compatible'

    object = objects[key]
    raise 'Snapshot is missing a database blob' unless object && object.fetch('size') == size
    path = File.join(directory, object.fetch('file'))
    raise 'Database blob checksum differs' unless Digest::MD5.file(path).base64digest == checksum
  end
  manifest
end

service = ActiveStorage::Blob.services.fetch('s3_compatible')
command, directory = ARGV
case command
when 'probe'
  key = "mesa-storage-checks/#{SecureRandom.hex(16)}"
  bytes = "Mesa Chatwoot OCI storage verification\n"
  checksum = Digest::MD5.base64digest(bytes)
  begin
    service.upload(key, StringIO.new(bytes), checksum: checksum, content_type: 'text/plain')
    raise 'Server upload/read failed' unless service.download(key) == bytes

    uri = URI(service.url_for_direct_upload(key, expires_in: 120, content_type: 'text/plain', content_length: bytes.bytesize,
                                               checksum: checksum))
    headers = service.headers_for_direct_upload(key, content_type: 'text/plain', checksum: checksum)
    origin = ENV.fetch('FRONTEND_URL')
    Net::HTTP.start(uri.host, uri.port, use_ssl: true, read_timeout: 30, open_timeout: 30) do |http|
      options = Net::HTTP::Options.new(uri)
      options['Origin'] = origin
      options['Access-Control-Request-Method'] = 'PUT'
      options['Access-Control-Request-Headers'] = 'content-type,content-md5'
      response = http.request(options)
      raise 'Direct upload preflight failed' unless response.is_a?(Net::HTTPSuccess) && ['*', origin].include?(response['access-control-allow-origin'])

      request = Net::HTTP::Put.new(uri, headers.merge('Origin' => origin))
      request.body = bytes
      response = http.request(request)
      raise 'Signed browser PUT failed' unless response.is_a?(Net::HTTPSuccess) && ['*', origin].include?(response['access-control-allow-origin'])
    end
    raise 'Direct upload bytes differ' unless service.download(key) == bytes

    signed = URI(service.url(key, expires_in: 120, disposition: :attachment, filename: ActiveStorage::Filename.new('verification.txt'),
                                  content_type: 'text/plain'))
    response = Net::HTTP.get_response(signed)
    raise 'Signed download failed' unless response.is_a?(Net::HTTPSuccess) && response.body == bytes
    raise 'Download disposition missing' unless response['content-disposition'].include?('verification.txt')

    signed.query = nil
    response = Net::HTTP.get_response(signed)
    raise 'Anonymous object access allowed' unless %w[403 404].include?(response.code)
    puts({ server_upload: true, signed_put: true, browser_cors: true, signed_download: true, anonymous_read_denied: true }.to_json)
  ensure
    service.delete(key)
  end
when 'migrate-local'
  local = ActiveStorage::Blob.services.fetch('local')
  blobs = ActiveStorage::Blob.order(:id).to_a
  raise 'Migration expects local blobs only' unless blobs.all? { |blob| blob.service_name == 'local' }

  files = Dir.glob(File.join(local.root, '**', '*')).select { |path| File.file?(path) }.sort
  sources = files.to_h do |path|
    key = Pathname.new(path).relative_path_from(Pathname.new(local.root)).each_filename.to_a.drop(2).join('/')
    raise 'Unexpected disk storage layout' unless local.send(:path_for, key) == path

    [key, { path: path, sha256: Digest::SHA256.file(path).hexdigest }]
  end
  raise 'Destination contains unrelated current objects' unless (inventory(service).keys - sources.keys).empty?

  blobs.each do |blob|
    source = sources.fetch(blob.key)
    raise 'Local size differs from database' unless File.size(source[:path]) == blob.byte_size
    raise 'Local checksum differs from database' unless Digest::MD5.file(source[:path]).base64digest == blob.checksum
  end
  sources.each do |key, source|
    unless service.exist?(key)
      blob = blobs.find { |item| item.key == key }
      File.open(source[:path], 'rb') do |file|
        service.upload(key, file, checksum: Digest::MD5.file(source[:path]).base64digest,
                                  content_type: blob&.content_type || 'application/octet-stream')
      end
    end
    raise 'Migrated bytes differ' unless remote_digest(service, key) == source[:sha256]
    raise 'Source changed during migration' unless Digest::SHA256.file(source[:path]).hexdigest == source[:sha256]
  end
  raise 'Database changed during migration' unless ActiveStorage::Blob.order(:id).pluck(:id) == blobs.map(&:id)

  ActiveStorage::Blob.transaction do
    count = ActiveStorage::Blob.where(id: blobs.map(&:id), service_name: 'local').update_all(service_name: 's3_compatible')
    raise 'Database references changed during migration' unless count == blobs.size
  end
  puts({ migrated_objects: sources.size, migrated_blobs: blobs.size, bytes: files.sum { |path| File.size(path) }, verified: true }.to_json)
when 'snapshot'
  raise 'Snapshot directory already exists' if File.exist?(directory)

  FileUtils.mkdir_p(File.join(directory, 'objects'), mode: 0o700)
  before = inventory(service)
  manifest = { format: 1, bucket: service.bucket.name, blobs: ActiveStorage::Blob.order(:id).pluck(:key, :byte_size, :checksum, :service_name),
               objects: [] }
  before.sort.each_with_index do |(key, expected), index|
    relative = format('objects/%08d', index)
    path = File.join(directory, relative)
    response = service.bucket.object(key).get(response_target: path, if_match: expected.fetch('etag'))
    raise 'Remote object size differs' unless File.size(path) == expected.fetch('size')

    manifest[:objects] << { key: key, file: relative, size: File.size(path), sha256: Digest::SHA256.file(path).hexdigest,
                            content_type: response.content_type, content_disposition: response.content_disposition, metadata: response.metadata }
  end
  raise 'Bucket changed during snapshot' unless inventory(service) == before

  File.write(File.join(directory, 'manifest.json'), JSON.generate(manifest))
  verify_snapshot(directory)
  puts({ snapshot_objects: before.size, verified: true }.to_json)
when 'verify', 'restore', 'restore-drill'
  manifest = verify_snapshot(directory)
  if command == 'restore'
    raise 'Restore requires an empty destination bucket' unless inventory(service).empty?

    manifest.fetch('objects').each do |object|
      File.open(File.join(directory, object.fetch('file')), 'rb') do |file|
        service.bucket.object(object.fetch('key')).put(body: file, content_type: object['content_type'],
                                                      content_disposition: object['content_disposition'], metadata: object.fetch('metadata'))
      end
      raise 'Restored bytes differ' unless remote_digest(service, object.fetch('key')) == object.fetch('sha256')
    end
  elsif command == 'restore-drill'
    # Unique keys only. Deletes create recoverable versioned delete markers; existing app objects are untouched.
    prefix = "mesa-restore-checks/#{SecureRandom.hex(16)}/"
    created = []
    begin
      manifest.fetch('objects').each_with_index do |object, index|
        key = prefix + index.to_s
        created << key
        File.open(File.join(directory, object.fetch('file')), 'rb') do |file|
          service.bucket.object(key).put(body: file, content_type: object['content_type'],
                                        content_disposition: object['content_disposition'], metadata: object.fetch('metadata'))
        end
        raise 'Restored bytes differ' unless remote_digest(service, key) == object.fetch('sha256')
        head = service.bucket.object(key)
        raise 'Restored metadata differs' unless head.content_type == object['content_type'] &&
                                               head.content_disposition == object['content_disposition'] && head.metadata == object.fetch('metadata')
      end
    ensure
      created.each { |key| service.delete(key) }
    end
  end
  puts({ command: command, verified_objects: manifest.fetch('objects').size, verified_blobs: manifest.fetch('blobs').size, verified: true }.to_json)
else
  raise 'Use probe, migrate-local, snapshot DIRECTORY, verify DIRECTORY, restore DIRECTORY or restore-drill DIRECTORY'
end
