const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const root = path.resolve(__dirname, '..');
const tools = JSON.parse(fs.readFileSync(path.join(root, 'outputs/android-tools.json'), 'utf8').replace(/^\uFEFF/, ''));
const name = 'PaseSeguro_API36';
const avdRoot = path.join(os.homedir(), '.android/avd');
const directory = path.join(avdRoot, name + '.avd');
fs.mkdirSync(directory, { recursive: true });
const configuration = {
  'AvdId': name, 'avd.ini.encoding': 'UTF-8', 'avd.ini.displayname': 'Residencial Segura Android 16',
  'PlayStore.enabled': 'false', 'abi.type': 'x86_64', 'hw.cpu.arch': 'x86_64', 'hw.cpu.ncore': '4',
  'hw.ramSize': '3072', 'hw.device.name': 'pixel_8', 'hw.device.manufacturer': 'Google',
  'hw.lcd.width': '1080', 'hw.lcd.height': '2400', 'hw.lcd.density': '420',
  'hw.gpu.enabled': 'yes', 'hw.gpu.mode': 'swiftshader_indirect', 'hw.keyboard': 'yes',
  'hw.camera.back': 'none', 'hw.camera.front': 'none', 'hw.audioInput': 'no',
  'image.sysdir.1': path.join(tools.SdkDirectory, 'system-images/android-36/google_apis/x86_64/'),
  'tag.id': 'google_apis', 'tag.display': 'Google APIs', 'target': 'android-36',
  'disk.dataPartition.size': '6G', 'showDeviceFrame': 'no', 'skin.dynamic': 'yes',
  'runtime.network.latency': 'none', 'runtime.network.speed': 'full',
};
fs.writeFileSync(path.join(directory, 'config.ini'), Object.entries(configuration).map(([key, value]) => `${key}=${value}`).join('\n') + '\n');
fs.writeFileSync(path.join(avdRoot, name + '.ini'), `avd.ini.encoding=UTF-8\npath=${directory}\npath.rel=avd/${name}.avd\ntarget=android-36\n`);
console.log('Test AVD created: ' + name);
