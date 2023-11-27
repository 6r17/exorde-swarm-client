
import logging, asyncio

blade_logger = logging.getLogger('blade')


async def spotting_process(batch):
    blade_logger.info("starting spotting process")

    await process_batch(batch)

    # upload_to_ipfs
        # download the uploaded file
        # count number of items
        # if != 0 next

    # transaction

    # get receipt
    blade_logger.info("spotting process complete")
