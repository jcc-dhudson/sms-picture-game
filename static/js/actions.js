$('#alertBtn').click(function () {
    $('#menuModal').modal('show')
})
$('#nav-sendToken').click(function(){
    $('#menuModal').modal('hide')
    $('#sendModal').modal('show')
})

$('#nav-submissions').click(function(){
    window.location.href = '/submissions';
})
$('#nav-groups').click(function(){
    window.location.href = '/admin';
})


sendModalOriginal = $('#sendModal').html()
$('#sendMessageButton').click(function(){
    modalOriginal = $('#sendModal').html()
    message = $('#sendMessageInput').val()
    max_uploads = $('#sendMaxUploads').val()
    console.log(max_uploads)
    rows = $table.bootstrapTable('getData')
    ids = []
    for (i = 0; i < rows.length; i++) {
        ids.push( rows[i].person_id )
    }
    
    console.log(message, ids)
    modalOriginal = $('#sendModal-body').html('Sending "'+message+'" and a link to '+ids.length+' participants.')
    $.ajax('/sendtoken', {
        data : JSON.stringify({'message': message, 'ids': ids, 'max_uploads': max_uploads}),
        contentType : 'application/json',
        type : 'POST',
    }).done(function(data){
        modalOriginal = $('#sendModal-body').html('Sent tokens. Server responded: <br />' + data)
    })
    $('#sendModal-footer').html('<button type="button" class="btn btn-secondary btn-block" id="sendAckBtn" >Acknowledge</button>')
    $('#sendAckBtn').click(function(){
        $('#sendModal').modal('hide')
        $('#sendModal').html(sendModalOriginal)
    })
    //$('#sendModal').modal('hide')
})

$('#nav-leaderboard').click(function(){
    $('#menuModal').modal('hide')
    $('#leaderboard-table-body').html('')
    $.get('/getscores', function(data){
        data.sort(function(a, b) {
            return b.score - a.score;
        });
        for (i = 0; i < data.length; i++) {
            $('#leaderboard-table-body').append('<tr><th scope="row">'+data[i].name+'</th><td><b><div style="font-size: large;" class="badge bg-light text-dark">'+data[i].score+'</div></b></td></tr>')
        }
        console.log(data)
    })

    $('#leaderboard').modal('show')
})

$('#nav-createGroup').click(function(){
    $('#menuModal').modal('hide')
    $('#createGroupBtn').click(function(){
        $.ajax('/groups', {
            data : JSON.stringify({'name': $('#groupName').val()}),
            contentType : 'application/json',
            type : 'POST',
        }).done(function(data){
            $('#groupName').val('')
            newGroup = {group_name: data.name, group_id: data.id, members: []}
            groups.push(newGroup)
            console.log(groups)
            $('#createGroupModal').modal('hide')
        })
    })
    $('#createGroupModal').modal('show')
})

$('#nav-deleteGroups').click(function(){
    $.ajax('/groups', {
        data : JSON.stringify({}),
        contentType : 'application/json',
        type : 'DELETE',
    }).done(function(data){
        groups = data
        $('#menuModal').modal('hide')
    })
})
