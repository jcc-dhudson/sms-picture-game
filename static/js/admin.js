
var $table = $('#fresh-table')
var groups = []
const options = {
  timeZone:"US/Eastern",
  hour12 : false,
  hour:  "2-digit",
  minute: "2-digit",
  second: "2-digit"
};


//
// when a check-in status message is clicked:
//
window.operateGroup = {
  'click .setGroup': function (e, value, row, index) {
    $('#groupModal-title').html(row.person_name + ' Group')
    var btnHtml = ''
    for (i = 0; i < groups.length; i++) {
        group = groups[i]
        if(group.group_id == row.group_id){
            btnHtml += '<button class="btn btn-primary" type="button">'+group.group_name+'</button>'
        } else {
            btnHtml += '<button class="groupAssign btn btn-secondary" type="button" data-person_id="'+row.person_id+'" data-group-id="'+group.group_id+'">'+group.group_name+'</button>'
        }
        
    }
    $('#groupModal-body').html(btnHtml)
    $('.groupAssign').click(function() {
        group_id = $(this).data('group-id')
        person_id = $(this).data('person_id')
        $.ajax('/assigngroup', {
            data : JSON.stringify({'group_id': group_id, 'person_id': person_id}),
            contentType : 'application/json',
            type : 'POST',
        }).done(function(){
            groupName = ''
            for (i = 0; i < groups.length; i++) {
                if (groups[i].group_id == group_id)
                    groupName = groups[i].group_name
            }
            $table.bootstrapTable('updateByUniqueId', {
                id: person_id,
                row: {
                    group_name: groupName,
                    group_id: group_id
                }})
        })
        $('#groupModal').modal('hide')
    })
    $('#groupModal').modal('show')
  }
}

$('button').click(function() {
   
})

//
// table formatters
//
function groupFormatter(value, row, index) {
    return '<button type="button" class="btn btn-outline-primary setGroup">'+value+'</button>'
}
function timeFormatter(value, row, index) {
  var dt = new Date(value * 1000);
  return dt.toLocaleString('en-US')
}
function sessionFormatter(value, row, index) {
  num = Math.round(Number(value))
  return '<a class="table-action setSearch" href="javascript:void(0)">'+num.toString(36)+'</a>'
}
function avatarFormatter(value, row, index) {
    return [
      '<img src="' + row.person_avatar + '" width="72px"/>'
    ].join('')
  }

$(function () {
  $table.bootstrapTable({
    classes: 'table table-hover table-striped',
    toolbar: '.toolbar',

    search: true,
    pagination: false,
    striped: true,
    sortable: true,
    uniqueId: "person_id",
    sortName: "datetime",
    sortOrder: "desc",
  })
})



$.get("/groups", function(data, status){
    groups = data
})