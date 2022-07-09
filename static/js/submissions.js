var $table = $('#fresh-table')
const options = {
    timeZone:"US/Eastern",
    hour12 : false,
    hour:  "2-digit",
    minute: "2-digit",
    second: "2-digit"
  };
var sasKey

window.operateStatus = {
    'click .status': function (e, value, row, index) {
        $('#scoreModal-submitScore').data('submission-id', row.id)
        $('#newScore').val(row.score)
        $('#scoreModal').modal('show')
        $.get('/getsasuri?rel=thumbs/' + row.transform.thumbnail, function(data){
            $('#put-thumb-uri-here').attr('src', data)
            if(row.transform.kind == 'image') {
                $('#scoreModal-body').html('<img  src="'+data+'" width="100%" />')
            } else if (row.transform.kind == 'video') {
                $('#scoreModal-body').html('<video width="100%" autoplay controls><source src="'+data+'"></video>')
            }
        })
        $('#setScore').off()
        $('#setScore').click(function(){
            $.ajax('/setscore/' + row.token, {
                data : JSON.stringify({score: $('#newScore').val()}),
                contentType : 'application/json',
                type : 'POST',
                
            }).done(function(){
                console.log(row)
                $table.bootstrapTable('updateByUniqueId', {
                    id: row.id,
                    row: {
                      score: $('#newScore').val(),
                      status: 'Scored'
                }})
                $('#scoreModal').modal('hide')
            })
        })
        $('#downloadOriginal').click(function(){
            filename = row.token + '_' + row.original_filename
            download('/getsasuri?download=' + row.token + '&filename=' + filename)
        })
    }
}
window.operateRound = {
    'click .round': function (e, value, row, index) {
        $table.bootstrapTable('resetSearch', row.round)
    }
}

//
// table formatters
//
function groupFormatter(value, row, index) {
    return '<b><div class="badge bg-light text-dark">'+ value + '</div></b>'
}
function statusFormatter(value, row, index) {
    if(value != undefined){
        return '<a class="table-action status" href="javascript:void(0)">'+ value + '</a>'
    }
}
function roundFormatter(value, row, index) {
    return '<div class="badge bg-warning text-dark round">'+ value + '</div>'
}

$(function () {
    $table.bootstrapTable({
      classes: 'table table-hover table-striped',
      toolbar: '.toolbar',
  
      search: true,
      pagination: false,
      striped: true,
      sortable: true,
      uniqueId: "id",
      sortName: "datetime",
      sortOrder: "desc",
    })
  })


  function download(fileUrl) {
    var a = document.createElement("a");
    a.href = fileUrl;
    a.click();
  }