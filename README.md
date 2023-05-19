# Textfile Collector Example Scripts

These scripts are examples to be used with the Node Exporter textfile
collector.

To use these scripts, we recommend using `sponge` to atomically write the
output.

```
<collector_script> | sponge <output_file>
```

Sponge comes from [moreutils](https://joeyh.name/code/moreutils/)
* [brew install moreutils](http://brewformulas.org/Moreutil)
* [apt install moreutils](https://packages.debian.org/search?keywords=moreutils)
* [pkg install moreutils](https://www.freshports.org/sysutils/moreutils/)

*Caveat*: sponge cannot write atomically if the path specified by the `TMPDIR`
environment variable is not on the same filesystem as the target output file.

For more information see:
https://github.com/prometheus/node_exporter#textfile-collector
