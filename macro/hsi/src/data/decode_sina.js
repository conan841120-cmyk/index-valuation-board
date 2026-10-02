// Isolated mathematical decoder: no network, no filesystem inside VM context.
const fs = require('fs');
const vm = require('vm');
const [input, decoder, output] = process.argv.slice(2);
const encoded = fs.readFileSync(input, 'utf8').match(/="([^"]+)"/)[1];
const code = fs.readFileSync(decoder, 'utf8');
const result = vm.runInNewContext(code + '\nJSON.stringify(d(payload))', {payload: encoded}, {timeout: 10000});
fs.writeFileSync(output, result);
