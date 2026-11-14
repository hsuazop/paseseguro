const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const readJSON = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));

(async () => {
  const tools = readJSON(path.join(root, 'outputs/android-tools.json'));
  const locations = readJSON(path.join(root, 'outputs/signing-locations.json'));
  const cli = path.join(process.env.APPDATA, 'npm/node_modules/@bubblewrap/cli');
  const { TwaManifest, TwaGenerator, ConsoleLog } = require(path.join(cli, 'node_modules/@bubblewrap/core'));
  const shared = require(path.join(cli, 'dist/lib/cmds/shared.js'));
  const directory = 'C:\\dev\\android\\paseseguro';
  fs.mkdirSync(directory, { recursive: true });
  const infoFile = path.join(locations.SigningDirectory, 'signing-info.json');
  const keyFile = path.join(locations.SigningDirectory, 'paseseguro.keystore');
  const packageId = 'com.paseseguro.app';
  const host = 'paseseguro.hectorsp25.opalstacked.com';
  const oldManifestFile = path.join(directory, 'twa-manifest.json');
  const oldManifest = fs.existsSync(oldManifestFile) ? readJSON(oldManifestFile) : {};
  if (oldManifest.packageId && oldManifest.packageId !== packageId) throw new Error('Existing Android project belongs to a different package.');
  const appVersion = process.argv[2] || oldManifest.appVersion || '1.0.0';
  const appVersionCode = Number(process.argv[3] || oldManifest.appVersionCode || 1);
  if (!Number.isSafeInteger(appVersionCode) || appVersionCode < 1) throw new Error('Invalid Android version code.');
  let info;
  if (fs.existsSync(infoFile)) {
    info = readJSON(infoFile);
    if (info.packageId !== packageId || info.alias !== 'paseseguro') throw new Error('Existing signing identity differs; preserving it.');
  } else {
    if (fs.existsSync(keyFile)) throw new Error('Existing keystore has no signing record; refusing to replace it.');
    const password = crypto.randomBytes(32).toString('base64url');
    info = { packageId, host, alias: 'paseseguro', keystorePath: keyFile, keystorePassword: password, keyPassword: password, createdAt: new Date().toISOString() };
    fs.writeFileSync(infoFile, JSON.stringify(info, null, 2), { mode: 0o600 });
  }
  const env = { ...process.env, PASESEGURO_KEYSTORE_PASSWORD: info.keystorePassword, PASESEGURO_KEY_PASSWORD: info.keyPassword };
  const keytool = path.join(tools.JdkDirectory, 'bin/keytool.exe');
  if (!fs.existsSync(keyFile)) {
    execFileSync(keytool, ['-genkeypair', '-keystore', keyFile, '-storetype', 'PKCS12', '-storepass:env', 'PASESEGURO_KEYSTORE_PASSWORD', '-keypass:env', 'PASESEGURO_KEY_PASSWORD', '-alias', info.alias, '-keyalg', 'RSA', '-keysize', '3072', '-sigalg', 'SHA256withRSA', '-validity', '10000', '-dname', 'CN=Pase Seguro,OU=Android,O=Pase Seguro,L=Tegucigalpa,C=HN', '-noprompt'], { env, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  }
  const certificateFile = path.join(directory, 'signing-certificate.der');
  execFileSync(keytool, ['-exportcert', '-keystore', keyFile, '-storepass:env', 'PASESEGURO_KEYSTORE_PASSWORD', '-alias', info.alias, '-file', certificateFile], { env, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  const fingerprint = crypto.createHash('sha256').update(fs.readFileSync(certificateFile)).digest('hex').toUpperCase().match(/.{2}/g).join(':');
  info.sha256Fingerprint = fingerprint;
  fs.writeFileSync(infoFile, JSON.stringify(info, null, 2), { mode: 0o600 });
  for (const file of [keyFile, infoFile]) fs.copyFileSync(file, path.join(locations.BackupDirectory, path.basename(file)));
  if (!fs.readFileSync(keyFile).equals(fs.readFileSync(path.join(locations.BackupDirectory, 'paseseguro.keystore')))) throw new Error('Signing backup verification failed.');

  const original = await TwaManifest.fromWebManifest(`https://${host}/manifest.webmanifest`);
  const twa = new TwaManifest({ ...original.toJson(), packageId, host, name: 'Pase Seguro', launcherName: 'Pase Seguro', appVersion, appVersionCode, minSdkVersion: 24, signingKey: { path: keyFile, alias: info.alias }, fingerprints: [{ name: 'Pase Seguro release', value: fingerprint }], generatorApp: 'bubblewrap-cli', display: 'standalone', orientation: 'any', enableNotifications: false, enableSiteSettingsShortcut: false, fallbackType: 'customtabs', navigationColor: '#153b63', navigationColorDark: '#153b63', themeColorDark: '#153b63', backgroundColor: '#f4f7fb' });
  const manifestFile = path.join(directory, 'twa-manifest.json');
  await twa.saveToFile(manifestFile);
  await new TwaGenerator().createTwaProject(directory, twa, new ConsoleLog('PaseSeguro'), (done, total) => console.log(`Android project: ${done}/${total}`));
  require('./patch-android-project.cjs')(directory);
  const appGradle = path.join(directory, 'app/build.gradle');
  fs.writeFileSync(appGradle, fs.readFileSync(appGradle, 'utf8').replace('androidbrowserhelper:2.7.+', 'androidbrowserhelper:2.7.4'));
  await shared.generateManifestChecksumFile(manifestFile, directory);
  const sdkPath = tools.SdkDirectory.replace(/\\/g, '/');
  fs.writeFileSync(path.join(directory, 'local.properties'), 'sdk.dir=' + sdkPath.replace(/:/g, '\\:') + '\n');
  fs.writeFileSync(path.join(directory, '.gitignore'), '.gradle/\n**/build/\nlocal.properties\n*.keystore\n*.jks\n*.apk\n*.aab\n');
  const assetlinks = [{ relation: ['delegate_permission/common.handle_all_urls'], target: { namespace: 'android_app', package_name: packageId, sha256_cert_fingerprints: [fingerprint] } }];
  fs.writeFileSync(path.join(directory, 'assetlinks.json'), JSON.stringify(assetlinks, null, 2));
  fs.writeFileSync(path.join(root, 'core/android-assetlinks.json'), JSON.stringify(assetlinks, null, 2) + '\n');
  fs.mkdirSync(path.join(root, 'outputs/android'), { recursive: true });
  fs.writeFileSync(path.join(root, 'outputs/android/build-identity.json'), JSON.stringify({ packageId, host, version: appVersion, versionCode: appVersionCode, fingerprint, projectDirectory: directory, signingDirectory: locations.SigningDirectory, backupDirectory: locations.BackupDirectory }, null, 2));
  console.log(JSON.stringify({ project: directory, packageId, fingerprint, signingBackup: locations.BackupDirectory }));
})().catch(error => { console.error(error); process.exitCode = 1; });
