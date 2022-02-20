#!/usr/bin/bash

 [ -d ./test-outputs ] && rm ./test-outputs/* || mkdir ./test-outputs
../src/Gmailtools/query_emails.py print_emails -s 'test1'
../src/Gmailtools/query_emails.py store_emails -s 'test1' --output test-outputs/test1.json -v
../src/Gmailtools/query_emails.py store_emails -a 01/31/2022 -b 02/03/2022  -v --output test-outputs/test2.json -v
../src/Gmailtools/query_emails.py download_attachments -s 'test2' -v --download_dir ./test-outputs
../src/Gmailtools/query_emails.py download_attachments -s 'test2' --force -v --download_dir ./test-outputs

../src/Gmailtools/query_emails.py print_emails -s 'test2' --await
