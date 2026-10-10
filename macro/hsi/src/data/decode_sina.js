// Execute only reviewed repository code; the VM timeout bounds decoding work.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const crypto = require('crypto');
if (process.argv.length !== 4) throw new Error('Usage: decode_sina.js input output');
const [input, output] = process.argv.slice(2);
const code = fs.readFileSync(path.join(__dirname, 'vendor/sina_hk_decode.js'));
if (crypto.createHash('sha256').update(code).digest('hex') !== '39a599c94dde4df1c2eb0882d4bff9560160cfd52ead0797cebb04b3122c2f52')
  throw new Error('Sina decoder SHA-256 mismatch');
const encoded = fs.readFileSync(input, 'utf8').match(/="([^"]+)"/)[1];
const result = vm.runInNewContext(code.toString('utf8') + '\nJSON.stringify(d(payload))', {payload: encoded}, {timeout: 10000});
fs.writeFileSync(output, result);
