const { BlobServiceClient } = require("@azure/storage-blob");
var pathname = window.location.pathname.split( '/' );
var token = pathname[2];
var tokenInfo
console.log(token)

var blobSasUrl
var blobServiceClient
var containerName
var containerClient
const fileInput = document.getElementById("#inputFile");
const status = document.getElementById("status");
const fileList = document.getElementById("file-list");

const reportStatus = message => {
    status.innerHTML += `${message}<br/>`;
    status.scrollTop = status.scrollHeight;
}


// <snippet_UploadBlobs>
const uploadFiles = async () => {
    try {
        reportStatus("Uploading files...");
        const promises = [];
        for (const file of fileInput.files) {
            const blockBlobClient = containerClient.getBlockBlobClient(file.name);
            promises.push(blockBlobClient.uploadBrowserData(file));
        }
        await Promise.all(promises);
        reportStatus("Done.");
        listFiles();
    }
    catch (error) {
            reportStatus(error.message);
    }
}

$('#submit').on('click', async function(e){
    var file = $('#inputFile').prop('files')[0];
    if (file != undefined && 'name' in file) {
        reportStatus("Uploading " + file.name);
        $("#submit").prop("disabled", true)
        $("#submit").hide()
        try {
            const promises = [];
            //newFile = new File([blob], file.name, {type: 'image/png'});
            const blockBlobClient = containerClient.getBlockBlobClient(token);
            promises.push(blockBlobClient.uploadBrowserData(file));
            await Promise.all(promises);
            reportStatus("Uploaded " + file.name);
            $.ajax('/submit/' + token, {
                data : JSON.stringify({filename: file.name}),
                contentType : 'application/json',
                type : 'POST',
                
            }).done(function(){
                reportStatus("Server accepted response");
                $('#uploadCard').html('<h3 align="center">Thank you. Your submission was received.</h3>')
            }).fail(function(){
                reportStatus("Server did not accept submission");
            })
            
            
        }
        catch (error) {
            reportStatus(error.message);
        }
    } else {
        reportStatus("You must select a file.");
    }
})

$.get("/playertoken/" + token, function(data, status){
    console.log(data)
    tokenInfo = data
    
    if( tokenInfo.group_upload_count != 0 && tokenInfo.group_upload_count >= tokenInfo.group_upload_max) {
        $('#uploadCard').html('<h3 align="center">'+tokenInfo.group_name+' has already submitted the maximum number of submissions.</h3>')
    } else {
        $('#header-userName').html(tokenInfo.person_name)
        $('#header-groupName').html(tokenInfo.group_name)
        blobSasUrl = tokenInfo.sas
        blobServiceClient = new BlobServiceClient(blobSasUrl);
        containerName = "uploads"
        containerClient = blobServiceClient.getContainerClient(containerName);
    }
}).fail(function(){
    $('#uploadCard').html('<h3 align="center">Error: Token '+token+' is not valid!</h3>')
})